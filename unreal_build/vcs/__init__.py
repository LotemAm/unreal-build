
def do_version_control(vcs_config: dict, build_metadata: dict) -> str:
    if 'perforce' in vcs_config:
        from unreal_build.vcs.perforce import Perforce
        vcs = Perforce(vcs_config['perforce'], build_metadata)
    elif 'git' in vcs_config:
        from unreal_build.vcs.git import Git
        vcs = Git(vcs_config['git'], build_metadata)
    else:
        raise ValueError('Unknown VCS method')

    vcs.sync()
    return vcs.get_commit_id()
