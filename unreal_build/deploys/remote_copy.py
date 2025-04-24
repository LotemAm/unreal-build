import logging
import subprocess
from pathlib import Path


class RemoteCopyDeployer:
    def __init__(
        self,
        host: str,
        user: str,
        destination_path: Path,
        certificate_path: str,
        kill_target: str = None
    ):
        self._host = host
        self.user = user
        self.dest_path = destination_path
        self.cert_path = certificate_path
        self.kill_target = kill_target

    @property
    def host(self) -> str:
        """Get the host address."""
        return self._host

    def deploy(self, build_dir: Path, build_metadata: dict):
        """Deploy the build to the remote host."""
        self.stop_running_server()
        self.copy_files(build_dir)

    def stop_running_server(self):
        """Stop any running server on the remote host."""
        if not self.kill_target:
            return
        logging.info(f"Stopping running server with target {self.kill_target}")
        ssh_cmd = f"ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {self.cert_path} {self.user}@{self.host} pkill -f {self.kill_target}"
        proc = subprocess.Popen(ssh_cmd, shell=True)
        return_code = proc.wait()
        logging.info(f"SSH process to kill target done with return code {return_code}")

    def copy_files(self, build_dir: Path):
        """Copy files to the remote host."""
        logging.info(f"Starting remote copy from {build_dir} to {self.user}@{self.host}:{self.dest_path}")
        scp_cmd = f"scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {self.cert_path} -r {build_dir} {self.destination}"
        proc = subprocess.Popen(scp_cmd, shell=True)
        return_code = proc.wait()
        logging.info(f"SCP process done with return code {return_code}")

    @property
    def destination(self) -> str:
        """Get the destination string for SCP."""
        return f"{self.user}@{self.host}:{self.dest_path}"
