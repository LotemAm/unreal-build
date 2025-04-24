import logging
import subprocess
from pathlib import Path
import tkinter as tk

import vdf


class SteamPipeDeployer:
    def __init__(self, steamcmdPath: str, appID: int, depotID: int, auth: dict, testDeployment: bool):
        self.steamcmd_path = steamcmdPath
        self.app_id = appID
        self.depot_id = depotID
        self.steam_auth = auth
        self.is_preview = testDeployment

    def deploy(self, build_dir: Path, build_metadata: dict):
        # if self.steam_auth['steamGuard']:
        #     self.authenticate_steam_guard()

        build_vdf_path = self.generate_build_vdf(build_dir, build_metadata)
        username = self.steam_auth["user"]
        steam_cmd = f'{self.steamcmd_path} +@NoPromptForPassword 1 +login {username} +run_app_build {build_vdf_path} +logout +quit'
        proc = subprocess.Popen(steam_cmd.split())
        return proc.wait() == 0

    def get_code_ui(self):
        result = None
        window = tk.Tk()
        window.title("Enter Steam Guard Code")
        window.attributes("-topmost", True)

        label = tk.Label(window, text="Enter Steam Guard code:")
        label.pack()

        code_entry = tk.Entry(window)
        code_entry.pack()

        def get_code():
            nonlocal result
            result = code_entry.get()
            window.destroy()  # Close the window after getting the code

        ok_button = tk.Button(window, text="OK", command=get_code)
        ok_button.pack()

        window.mainloop()

        if result is None or result == '':
            raise ValueError('Failed to get steam guard auth code')
        return result

    def authenticate_steam_guard(self):
        # run steamcmd set_steam_guard_code {code}
        code = self.get_code_ui()
        steam_cmd = f'{self.steamcmd_path} set_steam_guard_code {code} +quit'
        logging.info(f"Running steamcmd {steam_cmd}")
        proc = subprocess.Popen(steam_cmd.split())
        return proc.wait() == 0

    def generate_build_vdf(self, build_dir: Path, build_metadata: dict):
        # Read https://partner.steamgames.com/doc/sdk/uploading
        app_build = {
            'AppID': str(self.app_id),
            'Desc': f'Build commit = {build_metadata["commit_id"]}' if 'commit_id' in build_metadata else 'Unknown build',

            'Preview': '1' if self.is_preview else '0',
            # 'Local': "..\ContentServer\htdocs", // put content on local content server instead of uploading to Steam
            # "SetLive": "AlphaTest" // set this build live on a beta branch

            'ContentRoot': str(build_dir),
            'BuildOutput': str(build_dir.parent / 'SteamPipeOutput'),

            'Depots': {
                str(self.depot_id): {
                    'FileMapping': {
                        'LocalPath': '*',  # all files from ContentRoot folder
                        'DepotPath': '.',  # mapped into the root of the depot
                        'Recursive': '1',  # include all subfolders
                    },
                }
            }
        }

        build_vdf = vdf.VDFDict({'AppBuild': app_build})

        # Add exclusions - since these are duplicated keys, can't be done in dict
        build_vdf['AppBuild']['Depots'][str(self.depot_id)]['FileExclusion'] = '*.pdb'
        build_vdf['AppBuild']['Depots'][str(self.depot_id)]['FileExclusion'] = 'Saved*'

        vdf_file = build_dir.parent / 'app_build.vdf'
        with open(vdf_file, 'w') as out_file:
            vdf.dump(build_vdf, out_file)
        return vdf_file
