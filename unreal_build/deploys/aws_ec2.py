import logging
import time
from pathlib import Path

from ..utils import execute_cli_command
from .remote_copy import RemoteCopyDeployer


class AWSEC2Deployer(RemoteCopyDeployer):
    def __init__(
        self,
        instanceID: str,
        user: str,
        destinationPath: Path,
        certificatePath: str,
        killTarget: str = None,
        region: str = "us-east-1"
    ):
        # Initialize with a dummy host, we'll override the host property
        super().__init__("dummy-host", user, destinationPath, certificatePath, killTarget)
        self.instance_id = instanceID
        self.region = region
        self._public_ip = None

    def _get_instance_state(self) -> str:
        """Get the current state of the EC2 instance."""
        cmd = f"aws ec2 describe-instances --instance-ids {self.instance_id} --region {self.region} --query Reservations[0].Instances[0].State.Name --output text"
        return execute_cli_command(cmd)

    def _start_instance(self) -> None:
        """Start the EC2 instance if it's stopped."""
        logging.info(f"Starting instance {self.instance_id}")
        cmd = f"aws ec2 start-instances --instance-ids {self.instance_id} --region {self.region}"
        execute_cli_command(cmd)

    def _wait_for_instance_running(self) -> None:
        """Wait until the EC2 instance is in running state."""
        while True:
            state = self._get_instance_state()
            if state == "running":
                break
            logging.info("Waiting for instance to start...")
            time.sleep(5)

    def _get_public_ip(self) -> str:
        """Get the public IP address of the EC2 instance."""
        cmd = f"aws ec2 describe-instances --instance-ids {self.instance_id} --region {self.region} --query Reservations[0].Instances[0].PublicIpAddress --output text"
        return execute_cli_command(cmd)

    def _stop_instance(self) -> None:
        """Stop the EC2 instance."""
        state = self._get_instance_state()
        if state == "stopped":
            logging.info(f"Instance {self.instance_id} is already stopped")
            return

        logging.info(f"Stopping instance {self.instance_id}")
        cmd = f"aws ec2 stop-instances --instance-ids {self.instance_id} --region {self.region}"
        execute_cli_command(cmd)
        logging.info(f"Successfully initiated stop for instance {self.instance_id}")

    def deploy(self, build_dir: Path, build_metadata: dict):
        super().deploy(build_dir, build_metadata)
        self._stop_instance()

    @property
    def host(self) -> str:
        """Get the public IP of the EC2 instance, starting it if stopped."""
        if self._public_ip is None:
            state = self._get_instance_state()
            
            if state == "stopped":
                self._start_instance()
                self._wait_for_instance_running()
            
            self._public_ip = self._get_public_ip()
            logging.info(f"Retrieved public IP {self._public_ip} for instance {self.instance_id}")
        
        return self._public_ip
