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


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--zip',
        action='store_true',
        help='Zip the package after the build is completed'
    )
    parser.add_argument(
        '--remove-pdb',
        action='store_true',
        help='Remove PDB files after build is completed'
    )
    parser.add_argument(
        '--config',
        type=Path,
        default='config.yaml',
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
) -> str:
    uat_path = engine_path / 'Engine' / 'Build' / 'BatchFiles' / 'RunUAT.bat'
    engine_exe = engine_path / 'Engine' / 'Binaries' / 'Win64' / 'UnrealEditor-Win64-DebugGame-Cmd.exe'

    is_server = "server" in target.lower()
    cfg_str = f"-clientconfig={configuration}" if not is_server else f"-server -noclient -serverconfig={configuration}"

    return f"{uat_path} -ScriptsForProject={project_file} Turnkey -command=VerifySdk" \
           f" -platform={platform} -UpdateIfNeeded -project={project_file}" \
           f" BuildCookRun -nop4 -utf8output -nocompileeditor -skipbuildeditor -cook -project={project_file}" \
           f" -target={target} -unrealexe={engine_exe} -platform={platform} -stage -archive -package" \
           f" -build -pak -iostore -compressed -prereqs -archivedirectory={output_path}" \
           f" -manifests {cfg_str} -nocompile -nocompileuat"


def remove_files_by_ext(directory: Path, extensions: list[str]):
    for f in directory.iterdir():
        if f.is_dir():
            remove_files_by_ext(f, extensions)
        elif f.is_file():
            if f.suffix in extensions:
                f.unlink()


def main():
    args = parse_args()
    config = load_config(args.config)

    project_file = (Path(config['project']['path']) / config['project']['name']).with_suffix('.uproject')
    engine_path = Path(config['engine']['path'])
    output_path = Path(config['build']['outputPath']) / datetime.date.today().isoformat()
    output_path.mkdir(parents=True, exist_ok=True)

    targets = config['build']['targets']
    build_overrides = config['build'].get('override')
    if not build_overrides:
        build_overrides = list(range(targets))
    if not isinstance(build_overrides, (list, tuple)):
        build_overrides = [build_overrides]

    for i, target in enumerate(targets):
        if i not in build_overrides:
            logging.debug(f'Skipping build #{i}')
            continue

        platform = target['platform']
        target_name = target['target']
        build_configuration = target['configuration']
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
        print("Process done", proc.wait())

        if args.remove_pdb:
            remove_files_by_ext(output_path, ['.pdb', '.debug'])

        if args.zip:
            pass


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    main()
