import logging
import subprocess
from pathlib import Path
import shutil
import os
from string import Template

from unreal_build.utils import execute_cli_command


class DockerDeployer:
    def __init__(self, image: str, tag: str = "latest", push: bool = False):
        self.image = image
        self.tag = tag
        self.push = push
        self.full_image_name = f"{image}:{tag}"

    def deploy(self, build_dir: Path, build_metadata: dict):
        """Build and optionally push the Docker image."""
        logging.info(f"Building Docker image {self.full_image_name}")
        
        # Copy Dockerfile to build directory
        dockerfile_path = Path(__file__).parent / "files" / "Dockerfile"
        shutil.copy(dockerfile_path, build_dir / "Dockerfile")
        
        # Process and copy entrypoint script template
        entrypoint_path = Path(__file__).parent / "files" / "docker_entrypoint.sh.tpl"
        template = Template(entrypoint_path.read_text())
        entrypoint_content = template.substitute(
            target=build_metadata['target']
        )
        
        with open(build_dir / "docker-entrypoint.sh", 'w') as f:
            f.write(entrypoint_content)
        
        try:
            # Build the Docker image using build directory as context
            cmd = f"docker build -t {self.full_image_name} {build_dir}"
            execute_cli_command(cmd)
            
            if self.push:
                logging.info(f"Pushing Docker image {self.full_image_name}")
                cmd = f"docker push {self.full_image_name}"
                execute_cli_command(cmd)
                
        finally:
            # Clean up Dockerfile and entrypoint script
            (build_dir / "Dockerfile").unlink()
            (build_dir / "docker-entrypoint.sh").unlink()
