import json
import logging
import secrets
import urllib.error
import urllib.request
from pathlib import Path

from unreal_build.deploys.docker import DockerDeployer

EDGEGAP_API_BASE = "https://api.edgegap.com/v1"


class EdgeGapDeployer(DockerDeployer):
    """
    Builds and pushes a Docker image (reusing DockerDeployer), then updates an
    Edgegap application version to point at the newly pushed image tag.

    The configured `tag` is treated as a prefix; the final tag is
    `{tag}-{vcs_version}`, where `vcs_version` is the short VCS commit/change
    ID, or `unknown-{random hex}` if no VCS info is available.

    https://docs.edgegap.com/docs/api
    """

    def __init__(
        self,
        image: str,
        apiToken: str,
        appName: str,
        versionName: str,
        tag: str = "latest",
        push: bool = True,
    ):
        if not push:
            raise ValueError("push must be True for Edgegap deployments to ensure the container image is available.")

        super().__init__(image, tag, push)
        self.api_token = apiToken
        self.app_name = appName
        self.version_name = versionName

    @staticmethod
    def _get_vcs_tag_suffix(build_metadata: dict) -> str:
        commit_id = build_metadata.get('commit_id')
        if not commit_id:
            return f"unknown-{secrets.token_hex(4)}"
        return str(commit_id)[:8]

    def _split_image(self) -> tuple[str, str]:
        """Split `image` (e.g. "registry.edgegap.com/my-org-xxx/my-game-server") into
        (docker_repository, docker_image), i.e. the registry and the rest of the path."""
        repository, _, rest = self.image.partition("/")
        if not rest:
            raise ValueError(f"image '{self.image}' must include a repository, e.g. 'registry.example.com/org/image'")
        return repository, rest

    def _update_version(self):
        """Update the Edgegap app version to point at the newly pushed image tag."""
        logging.info(f"Updating Edgegap version {self.app_name}:{self.version_name} to image {self.full_image_name}")
        url = f"{EDGEGAP_API_BASE}/app/{self.app_name}/version/{self.version_name}"
        docker_repository, docker_image = self._split_image()
        payload = {
            "docker_repository": docker_repository,
            "docker_image": docker_image,
            "docker_tag": self.tag,
        }
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode(),
            headers={
                "authorization": f"token {self.api_token}",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
        try:
            with urllib.request.urlopen(request) as response:
                logging.info(f"Edgegap version {self.version_name} updated successfully: {response.status}")
        except urllib.error.HTTPError as e:
            logging.error(f"Failed to update Edgegap version {self.version_name}: {e.code} {e.read().decode()}")
            raise

    def deploy(self, build_dir: Path, build_metadata: dict):
        tag_suffix = self._get_vcs_tag_suffix(build_metadata)
        self.tag = f"{self.tag}-{tag_suffix}"
        self.full_image_name = f"{self.image}:{self.tag}"

        super().deploy(build_dir, build_metadata)

        self._update_version()
