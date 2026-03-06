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
        files_dir = Path(__file__).parent / "files"
        shutil.copy(files_dir / ".dockerignore", build_dir / ".dockerignore")

        target = build_metadata['target']
        project_name = build_metadata['project_name']
        target_platform = build_metadata['platform']
        configuration = build_metadata['configuration']

        executable = f"/server/{project_name}/Binaries/{target_platform}/{target}-{target_platform}-{configuration}"

        template = Template((files_dir / "Dockerfile.tpl").read_text())
        dockerfile_content = template.substitute(
            tpl_executable=executable,
            tpl_project_name=project_name
        )

        with open(build_dir / "Dockerfile", 'w', newline='\n') as f:
            f.write(dockerfile_content)
        
        try:
            # Build the Docker image using build directory as context
            arm64_platform = "--platform linux/arm64" if build_metadata.get('is_arm64', False) else ""
            cmd = f"docker build {arm64_platform} -t {self.full_image_name} {build_dir}"
            execute_cli_command(cmd)
            
            if self.push:
                logging.info(f"Pushing Docker image {self.full_image_name}")
                cmd = f"docker push {self.full_image_name}"
                execute_cli_command(cmd)
                
        finally:
            # Clean up Dockerfile and entrypoint script
            (build_dir / "Dockerfile").unlink()
            (build_dir / ".dockerignore").unlink()
