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
from unreal_build.vcs import do_version_control


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--no-build',
        action='store_true',
        help='Skip building (and only deploy)'
    )
    parser.add_argument(
        '--no-deploy',
        action='store_true',
        help='Don\'t deploy after building'
    )
    parser.add_argument(
        '--no-symbols',
        action='store_true',
        help='Build without symbols (debug info)'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default='../config.yaml',
        help='Specify config file path (default: ../config.yaml)'
    )
    parser.add_argument(
        '--override',
        type=int,
        nargs='+',
        help='Specify which build to override'
    )
    return parser.parse_args()


def load_config(path: Path) -> dict:
    with open(path, 'r') as file:
        if path.suffix == '.yaml' or path.suffix == '.yml':
            if yaml is None:
                raise ImportError("YAML support requires PyYAML to be installed.")
            return yaml.safe_load(file)
        if path.suffix == '.json':
            return json.load(file)
        raise ValueError(f"Unsupported config file format: {path.suffix}")


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

    is_server = "server" in target.lower()
    cfg_str = f"-clientconfig={configuration}" if not is_server else f"-server -noclient -serverconfig={configuration}"

    return f"{uat_path} BuildCookRun -noP4 -project={project_file} -platform={platform} {cfg_str}" \
           f" -target={target} -cook -allmaps -build -stage -pak -archive -archivedirectory={output_path}" \
           f" -skipeditorcontent -compressed" \
           f" {'' if with_symbols else '-nodebuginfo'}"


def remove_files_by_ext(directory: Path, extensions: list[str]):
    for f in directory.iterdir():
        if f.is_dir():
            remove_files_by_ext(f, extensions)
        elif f.is_file():
            if f.suffix in extensions:
                f.unlink()


def get_build_overrides(args, config, targets):
    if args.override is not None:
        config['build']['override'] = args.override
    build_overrides = config['build'].get('override')
    if build_overrides is None:
        build_overrides = list(range(len(targets)))
    if not isinstance(build_overrides, (list, tuple)):
        build_overrides = [build_overrides]
    return build_overrides


def main():
    args = parse_args()
    config = load_config(args.config)

    project_name = config['project']['name']
    project_path = config['project']['path']

    build_metadata = {
        'project_name': project_name,
        'project_path': project_path,
    }

    if not args.no_build and (vcs_config := config.get('vcs')):
        if vcs_config.get('enabled', False):
            commit_id = do_version_control(vcs_config, build_metadata)
            build_metadata['commit_id'] = commit_id
    project_file = (Path(config['project']['path']) / project_name).with_suffix('.uproject')
    engine_path = Path(config['engine']['path'])
    output_path = Path(config['build']['outputPath']) / datetime.date.today().isoformat()
    output_path.mkdir(parents=True, exist_ok=True)

    targets = config['build']['targets']
    build_overrides = get_build_overrides(args, config, targets)

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
        with_symbols = target.get('symbols', False)
        if with_symbols and args.no_symbols:
            with_symbols = False

        build_metadata.update({
            'platform': platform,
            'target': target_name,
            'configuration': build_configuration,
            'is_arm64': 'arm64' in platform.lower(),
        })

        platform_full = 'Windows' if platform in ['Win64', 'Win32'] else platform
        build_directory = output_path / f'{platform_full}{"Server" if "Server" in target_name else ""}'

        if not args.no_build:
            logging.info(f"Starting build for {platform = } {target_name = } {build_configuration = }\n{'=' * 100}\n")
            cmd = build_uat_command(
                engine_path,
                project_file,
                platform,
                target_name,
                build_configuration,
                output_path,
                with_symbols=with_symbols
            )
            proc = subprocess.Popen(cmd.split())
            return_code = proc.wait()
            logging.info(f"Build process done with return code {return_code}")
            if return_code != 0:
                raise RuntimeError(f"Build failed with return code {return_code}")

        if steam_app_id := target.get('steam_appid.txt'):
            steam_app_id_path = build_directory / project_name / 'Binaries' / platform / 'steam_appid.txt'
            logging.info(f"Writing Steam App ID to {steam_app_id_path}")
            steam_app_id_path.write_text(str(steam_app_id))

        if not args.no_deploy and (deploy_config := target.get('deploy')):
            deploy_build(
                deploy_config,
                build_directory,
                build_metadata
            )

        logging.info(f"Done running on {target_name}")


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    main()
