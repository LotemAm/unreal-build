import logging

from P4 import P4, P4Exception


class Perforce:
    def __init__(self, vcs_config: dict, build_metadata: dict):
        self.config = vcs_config
        workspace = self.config['workspace']
        username = self.config['username']
        password = self.config['password']

        self.p4 = P4()
        self.p4.user = username
        self.p4.password = password
        self.p4.client = workspace

    def sync(self):
        try:
            logging.info("Syncing Perforce workspace...")
            self.p4.connect()
            self.p4.run_login()
            self.p4.run_sync()
            logging.info("Perforce workspace synced successfully")
        except P4Exception as e:
            if 'File(s) up-to-date.' in str(e):
                logging.info("Perforce workspace already up-to-date")
                return
            logging.error(f"Failed to sync Perforce workspace: {e}")
            raise

    def get_commit_id(self):
        try:
            logging.info("Getting Perforce changelist ID...")
            self.p4.connect()
            self.p4.run_login()
            changelists = self.p4.run_changes('-m1', '//...')
            if changelists:
                changelist_id = changelists[0]['change']
                logging.info(f"Latest Perforce changelist ID: {changelist_id}")
                return changelist_id
            else:
                logging.info("No changelists found")
                return None
        except P4Exception as e:
            logging.error(f"Failed to get Perforce changelist ID: {e}")
            raise
