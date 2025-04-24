import logging
from git import Repo
from pathlib import Path


class Git:
    def __init__(self, vcs_config: dict, build_metadata: dict):
        self.config = vcs_config
        self.repo = Repo(build_metadata['project_path'])

    def sync(self):
        """Sync the local git repository with the remote."""
        logging.info("Syncing Git repository...")
        
        # Check for uncommitted changes
        if self.repo.is_dirty():
            changes = self.repo.index.diff(None)
            untracked = self.repo.untracked_files
            error_msg = "Cannot sync: There are uncommitted changes:\n"
            if changes:
                error_msg += "Modified files:\n" + "\n".join(f"- {d.a_path}" for d in changes) + "\n"
            if untracked:
                error_msg += "Untracked files:\n" + "\n".join(f"- {f}" for f in untracked)
            logging.error(error_msg)
            raise RuntimeError("Cannot sync with uncommitted changes. Please commit or stash your changes first.")
        
        # Perform the sync
        if 'branch' in self.config and self.config['branch']:
            branch = self.config['branch']
            try:
                self.repo.git.checkout(branch)
            except Exception as e:
                logging.error(f"Failed to checkout branch {branch}: {e}")
                raise
        self.repo.remotes.origin.fetch()
        logging.info("Git repository synced successfully")

    def get_commit_id(self):
        """Get the current commit hash of the local git repository."""
        commit_id = self.repo.head.commit.hexsha
        logging.info(f"Current Git commit ID: {commit_id}")
        return commit_id
