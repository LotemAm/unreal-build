import pathlib


def deploy_build(deploy_config: dict, build_path: pathlib.Path, build_metadata: dict):
    if 'steam' in deploy_config:
        from unreal_build.deploys.steam import SteamPipeDeployer
        deployer = SteamPipeDeployer(**deploy_config['steam'])
    elif 'remoteCopy' in deploy_config:
        from unreal_build.deploys.remote_copy import RemoteCopyDeployer
        deployer = RemoteCopyDeployer(**deploy_config['remoteCopy'])
    elif 'awsEC2' in deploy_config:
        from unreal_build.deploys.aws_ec2 import AWSEC2Deployer
        deployer = AWSEC2Deployer(**deploy_config['awsEC2'])
    elif 'docker' in deploy_config:
        from unreal_build.deploys.docker import DockerDeployer
        deployer = DockerDeployer(**deploy_config['docker'])
    else:
        raise ValueError('Unknown deploy method')

    return deployer.deploy(
        build_path,
        build_metadata
    )
