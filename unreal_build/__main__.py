import argparse
import datetime
import logging
import subprocess
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None
    import json

from unreal_build.deploys import deploy_build


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--no-build',
        action='store_true',
        help='Skip building (and only deploy)'
    )
    parser.add_argument(
        '--zip',
        action='store_true',
        help='Zip the package after the build is completed'
    )
    parser.add_argument(
        '--no-symbols',
        action='store_true',
        help='Remove PDB files after build is completed'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default='../config.yaml',
        help='Specify config file path'
    )
    return parser.parse_args()


def load_config(path: Path) -> dict:
    with open(path, 'r') as file:
        if not yaml:
            return json.load(file)
        return yaml.safe_load(file)


def build_uat_command(
        engine_path: Path,
        project_file: Path,
        platform: str,
        target: str,
        configuration: str,
        output_path: Path,
        with_symbols: bool = True,
) -> str:
    uat_path = engine_path / 'Engine' / 'Build' / 'BatchFiles' / 'RunUAT.bat'
    # engine_exe = engine_path / 'Engine' / 'Binaries' / 'Win64' / 'UnrealEditor-Win64-DebugGame-Cmd.exe'

    is_server = "server" in target.lower()
    cfg_str = f"-clientconfig={configuration}" if not is_server else f"-server -noclient -serverconfig={configuration}"

    return f"{uat_path} BuildCookRun -noP4 -project={project_file} -platform={platform} {cfg_str}" \
           f" -target={target} -cook -allmaps -build -stage -pak -archive -archivedirectory={output_path}" \
           f" {'' if with_symbols else '-nodebuginfo'}"


def remove_files_by_ext(directory: Path, extensions: list[str]):
    for f in directory.iterdir():
        if f.is_dir():
            remove_files_by_ext(f, extensions)
        elif f.is_file():
            if f.suffix in extensions:
                f.unlink()


def do_version_control(vcs_config: dict):
    from P4 import P4, P4Exception

    perforce = vcs_config.get('perforce')
    if perforce is None:
        logging.warning("VCS is enabled but no perforce settings")
        return
    logging.debug("Pulling from Perforce")
    workspace = perforce['workspace']
    username = perforce['username']
    password = perforce['password']

    if not all((workspace, username, password)):
        logging.warning("Missing Perforce settings")
        return

    p4 = P4()
    p4.user = username
    p4.password = password
    p4.client = workspace
    try:
        p4.connect()
        p4.run_login()
        p4.run_sync()
        logging.info("Perforce synced")
    except P4Exception as e:
        # If any errors occur, we'll jump in here. Just log them
        # and raise the exception up to the higher level
        if 'File(s) up-to-date.' in str(e):
            logging.info("Perforce already up-to-date")
            return
        raise


def main():
    args = parse_args()
    config = load_config(args.config)

    if not args.no_build and (vcs_config := config.get('vcs')):
        if vcs_config.get('enabled', False):
            do_version_control(vcs_config)

    project_file = (Path(config['project']['path']) / config['project']['name']).with_suffix('.uproject')
    engine_path = Path(config['engine']['path'])
    output_path = Path(config['build']['outputPath']) / datetime.date.today().isoformat()
    output_path.mkdir(parents=True, exist_ok=True)

    targets = config['build']['targets']
    build_overrides = config['build'].get('override')
    if build_overrides is None:
        build_overrides = list(range(len(targets)))
    if not isinstance(build_overrides, (list, tuple)):
        build_overrides = [build_overrides]

    for i, target in enumerate(targets):
        if i not in build_overrides:
            logging.debug(f'Skipping build #{i}')
            continue

        if target.get('disabled', False):
            logging.debug(f'Skipping disabled build')
            continue

        platform = target['platform']
        target_name = target['target']
        build_configuration = target['configuration']

        platform_full = 'Windows' if platform in ['Win64', 'Win32'] else 'Linux'
        build_directory = output_path / f'{platform_full}{"Server" if "Server" in target_name else ""}'

        if not args.no_build:
            logging.info(f"Starting build for {platform = } {target_name = } {build_configuration = }\n{'=' * 100}\n")
            cmd = build_uat_command(
                engine_path,
                project_file,
                platform,
                target_name,
                build_configuration,
                output_path
            )
            proc = subprocess.Popen(cmd.split())
            return_code = proc.wait()
            logging.info(f"Build process done with return code {return_code}")

            if args.remove_pdb:
                remove_files_by_ext(build_directory, ['.pdb', '.debug', '.sym'])

            if args.zip:
                pass

        if deploy_config := target.get('deploy'):
            deploy_build(deploy_config, build_directory)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
