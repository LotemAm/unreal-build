import logging
import subprocess
from pathlib import Path


def deploy_remote_copy(host: str, user: str, dest_path: Path, cert_path: str, build_dir: Path):
    logging.info(f"Starting remote copy from {build_dir} to {user}@{host}:{dest_path}")
    scp_cmd = f"scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null -i {cert_path} -r {build_dir} {user}@{host}:{dest_path}"
    proc = subprocess.Popen(scp_cmd.split())
    return_code = proc.wait()
    logging.info(f"SCP process done with return code {return_code}")
