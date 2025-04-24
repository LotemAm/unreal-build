import subprocess


def execute_cli_command(cmd: str) -> str:
    """
    Execute a CLI command and return its output.
    
    Args:
        cmd: The command to execute
        
    Returns:
        The command output as a string
        
    Raises:
        Exception: If the command fails
    """
    proc = subprocess.Popen(cmd.split(), shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = proc.communicate()
    
    if proc.returncode != 0:
        raise Exception(f"Command failed: {stderr.decode()}")
    
    return stdout.decode().strip()
