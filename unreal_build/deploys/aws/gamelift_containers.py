import json
import logging
import time
from pathlib import Path

from unreal_build.utils import execute_cli_command
from unreal_build.deploys.docker import DockerDeployer


class GameLiftContainerDeployer(DockerDeployer):
    """
    Deploys a build to AWS GameLift managed containers using a container image
    This will build and push a Docker image, then deploy it to GameLift managed containers

    Requires GameLift managed containers and a container group definition to be set up
    """
    def __init__(
        self,
        image: str,
        containerGroupDefinitionName: str,
        managedContainerFleetId: str,
        tag: str = "latest",
        push: bool = True,
        region: str = "us-east-1",
        containerName: str = None
    ):
        if not push:
            raise ValueError("push must be True for GameLift deployments to ensure the container image is available.")
            
        super().__init__(image, tag, push)
        self.container_group_definition_name = containerGroupDefinitionName
        self.managed_container_fleet_id = managedContainerFleetId
        self.region = region
        self.container_name = containerName

    def _get_container_group_definition(self) -> dict:
        cmd = f"aws gamelift describe-container-group-definition --name {self.container_group_definition_name} --region {self.region}"
        output = execute_cli_command(cmd)
        return json.loads(output)

    def _create_container_group_definition_version(self, container_definition, version_description: str = None) -> int:
        # Prepare container definitions for CLI (escape quotes if necessary, or write to temp file)
        # Writing to a temp file is safer for complex JSON
        import tempfile
        import os
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump(container_definition, f)
            temp_path = f.name

        try:
            cmd = f"aws gamelift update-container-group-definition --name {self.container_group_definition_name} \
            --game-server-container-definition file://{temp_path} --region {self.region}".split()
            if version_description:
                cmd.extend(["--version-description", version_description])
            
            output = execute_cli_command(cmd)
            result = json.loads(output)
            return result['ContainerGroupDefinition']['VersionNumber']
        finally:
            os.unlink(temp_path)

    def _get_fleet_capacities(self) -> dict:
        """
        Returns a dict of {location: desired_instances} for the fleet.
        """
        # 1. Get all locations
        cmd = f"aws gamelift describe-fleet-location-attributes --fleet-id {self.managed_container_fleet_id} --region {self.region}"
        output = execute_cli_command(cmd)
        data = json.loads(output)
        
        locations = []
        for loc_attr in data.get('LocationAttributes', []):
            loc = loc_attr['LocationState']['Location']
            if loc:
                locations.append(loc)
        
        # 2. Get capacity for each location
        capacities = {}
        for location in locations:
            cmd = f"aws gamelift describe-fleet-location-capacity --fleet-id {self.managed_container_fleet_id} \
            --location {location} --region {self.region}"
            output = execute_cli_command(cmd)
            cap_data = json.loads(output)
            
            fleet_capacity = cap_data.get('FleetCapacity', {})
            desired = fleet_capacity.get('InstanceCounts', {}).get('Desired', 0)
            capacities[location] = desired
            
        return capacities

    def _set_location_capacity(self, location: str, desired_instances: int):
        logging.info(f"Scaling location {location} to {desired_instances} instances")
        cmd = f"aws gamelift update-fleet-capacity --fleet-id {self.managed_container_fleet_id} --location {location} --desired-instances {desired_instances} --max-size {desired_instances} --region {self.region}"
        execute_cli_command(cmd)

    def _wait_for_locations_active(self, locations: list, timeout: int = 600):
        """
        Waits for the specified locations to reach ACTIVE status.
        """
        logging.info(f"Waiting for locations {locations} to be ACTIVE...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            cmd = f"aws gamelift describe-fleet-location-attributes --fleet-id {self.managed_container_fleet_id} --locations {' '.join(locations)} --region {self.region}"
            output = execute_cli_command(cmd)
            data = json.loads(output)
            
            all_active = True
            for loc_attr in data.get('LocationAttributes', []):
                status = loc_attr.get('LocationState').get('Status')
                loc_name = loc_attr.get('LocationState').get('Location')
                if status != 'ACTIVE':
                    logging.info(f"Location {loc_name} status: {status}")
                    all_active = False
            
            if all_active:
                logging.info("All locations are ACTIVE.")
                return
            
            time.sleep(10)
            
        raise TimeoutError(f"Timed out waiting for locations {locations} to be ACTIVE")

    def _wait_for_container_group_definition_ready(self, version_number: int, timeout: int = 600):
        """
        Waits for the container group definition version to reach READY status.
        """
        logging.info(f"Waiting for container group definition {self.container_group_definition_name}:{version_number} to be READY...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            cmd = f"aws gamelift describe-container-group-definition --name {self.container_group_definition_name} --version-number {version_number} --region {self.region}"
            output = execute_cli_command(cmd)
            data = json.loads(output)
            
            cgd = data.get('ContainerGroupDefinition', {})
            status = cgd.get('Status')
            
            if status == 'READY':
                logging.info(f"Container group definition {version_number} is READY.")
                return
            elif status == 'COPYING':
                logging.info(f"Container group definition status: {status}...")
            elif status == 'FAILED':
                raise Exception(f"Container group definition {version_number} FAILED: {cgd.get('StatusReason')}")
            else:
                logging.info(f"Container group definition status: {status}")
            
            time.sleep(5)
            
        raise TimeoutError(f"Timed out waiting for container group definition {version_number} to be READY")

    def _update_fleet(self, version_number: int):
        # Construct the full definition identifier with version
        definition_identifier = f"{self.container_group_definition_name}:{version_number}"
        
        # 1. Check capacities and scale up if necessary
        original_capacities = self._get_fleet_capacities()
        scaled_locations = []
        
        try:
            for location, capacity in original_capacities.items():
                if capacity == 0:
                    logging.info(f"Location {location} has 0 capacity. Scaling up to 1 for update.")
                    self._set_location_capacity(location, 1)
                    scaled_locations.append(location)
            
            # 2. Wait for all locations to be ACTIVE (if we scaled any)
            # Even if we didn't scale, we should probably check if they are active before updating?
            # The error says "Please scale up fleet... before attempting to update".
            # It implies we need > 0 capacity.
            # Also need to wait for them to be ACTIVE.
            if scaled_locations:
                self._wait_for_locations_active(scaled_locations)
            
            # 3. Update Fleet
            logging.info(f"Updating fleet {self.managed_container_fleet_id} to use container group definition {definition_identifier}")
            cmd = f"aws gamelift update-container-fleet --fleet-id {self.managed_container_fleet_id} --game-server-container-group-definition-name {self.container_group_definition_name} --region {self.region}"
            execute_cli_command(cmd)

            # Small delay to allow the update to initiate properly
            logging.debug("Waiting 45 seconds to allow fleet update to initiate...")
            time.sleep(45)

            # 4. Wait for update to propagate/locations to be ACTIVE again
            # After update-container-fleet, the fleet goes into UPDATING or similar.
            # We need to wait for it to be ACTIVE before we can scale down.
            # We should wait for ALL locations to be ACTIVE.
            all_locations = list(original_capacities.keys())
            self._wait_for_locations_active(all_locations, 60*20)
            
        finally:
            pass
            # 5. Restore original capacities
            if scaled_locations:
                logging.info("Restoring original capacities for scaled locations...")
                for location in scaled_locations:
                    # We know original was 0
                    self._set_location_capacity(location, 0)
                
                # Optional: Wait for scale down? Probably not strictly necessary for the script to finish,
                # but good for cleanliness.
                # self._wait_for_locations_active(scaled_locations)

    def deploy(self, build_dir: Path, build_metadata: dict):
        # 1. Build and Push Docker Image
        super().deploy(build_dir, build_metadata)

        # 2. Get current Container Group Definition
        logging.info(f"Fetching container group definition: {self.container_group_definition_name}")
        cgd = self._get_container_group_definition()
        
        if 'ContainerGroupDefinition' not in cgd:
            raise ValueError(f"Could not find ContainerGroupDefinition in response: {cgd}")
             
        cgd_data = cgd['ContainerGroupDefinition']
        
        # Determine Version Description
        commit_id = build_metadata.get('commit_id', 'unknown')
        version_description = f'git commit {commit_id}'
        
        container_definition = None
        
        # 3. Update the Container Definition with new image
        if 'GameServerContainerDefinition' in cgd_data:
            # Handle single object (Game Server)
            container_definition = cgd_data['GameServerContainerDefinition']
            
            # Remove read-only fields that might cause issues on update
            container_definition.pop('ResolvedImageDigest', None)
            
            current_image = container_definition.get('ImageUri', '')
            should_update = False
            
            if self.container_name and container_definition.get('ContainerName') == self.container_name:
                should_update = True
            elif not self.container_name:
                # Heuristic: if the image URI starts with the configured image repo
                if current_image.startswith(self.image):
                    should_update = True
            
            if should_update:
                logging.info(f"Updating container '{container_definition.get('ContainerName')}' image to {self.full_image_name}")
                container_definition['ImageUri'] = self.full_image_name
            else:
                logging.warning(f"Container definition image {current_image} did not match {self.image}. Creating new version with existing definition.")
                
        elif 'ContainerDefinitions' in cgd_data:
            # Handle list (Legacy/Other)
            container_definition = cgd_data['ContainerDefinitions']
            updated = False
            for container in container_definition:
                # Remove read-only fields if present
                container.pop('ResolvedImageDigest', None)
                
                current_image = container.get('ImageUri', '')
                should_update = False
                if self.container_name and container['ContainerName'] == self.container_name:
                    should_update = True
                elif not self.container_name:
                    if current_image.startswith(self.image):
                        should_update = True
                
                if should_update:
                    logging.info(f"Updating container '{container['ContainerName']}' image to {self.full_image_name}")
                    container['ImageUri'] = self.full_image_name
                    updated = True
            
            if not updated:
                logging.warning(f"No container definition found matching image {self.image} or name {self.container_name}. Creating new version with existing definitions.")
        else:
            raise ValueError("Could not find GameServerContainerDefinition or ContainerDefinitions in response.")

        # 4. Create new Container Group Definition Version
        logging.info("Creating new container group definition version...")
        new_version = self._create_container_group_definition_version(container_definition, version_description)
        logging.info(f"Created version {new_version}")

        # 5. Wait for Container Group Definition to be READY
        self._wait_for_container_group_definition_ready(new_version)

        # 6. Update Fleet
        self._update_fleet(new_version)
        logging.info("Fleet update initiated.")
