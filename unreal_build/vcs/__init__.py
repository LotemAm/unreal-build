
def do_version_control(vcs_config: dict):
    if 'perforce' in vcs_config:
        from unreal_build.vcs.perforce import Perforce
        vcs = Perforce(vcs_config['perforce'])
    elif 'git' in vcs_config:
        from unreal_build.vcs.git import Git
        vcs = Git(vcs_config['git'])
    else:
        raise ValueError('Unknown VCS method')

    vcs.sync()
    return vcs.get_commit_id()
