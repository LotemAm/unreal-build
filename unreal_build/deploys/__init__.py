import pathlib


def deploy_build(deploy_config: dict, build_path: pathlib.Path):
    if 'steam' in deploy_config:
        return
    if 'remoteCopy' in deploy_config:
        from unreal_build.deploys.remote_copy import deploy_remote_copy
        remote_copy_config = deploy_config['remoteCopy']
        return deploy_remote_copy(
            remote_copy_config['host'],
            remote_copy_config['user'],
            remote_copy_config['destinationPath'],
            remote_copy_config['certificatePath'],
            build_path
        )
