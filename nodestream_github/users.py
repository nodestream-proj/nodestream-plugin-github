"""
Nodestream Extractor that creates GitHub user nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from typing import AsyncIterator

import httpx
from nodestream.pipeline import Extractor

from .interpretations.relationship.repository import simplify_repo
from .types import SimplifiedRepo, UserRecord
from .util import GithubRestApiClient, PermissionCategory, PermissionName, init_logger

logger = init_logger(__name__)


class GithubUserExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[UserRecord]:
        """Scrapes the GitHub REST api for all users and converts them to records.

        https://docs.github.com/en/enterprise-server@3.12/rest/users/users?apiVersion=2022-11-28#list-users
        """
        async for user in self.client.get("users"):
            if user["type"] != "User":
                continue  # github returns both users and orgs as users

            login = user["login"]
            user["repositories"] = [repo async for repo in self._fetch_repos(login)]
            yield user

    async def _fetch_repos(self, login: str) -> AsyncIterator[SimplifiedRepo]:
        """Fetch public repositories for the specified user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        Fine-grained token must have the "Metadata" repository permissions (read)
        """
        try:
            async for response in self.client.get(
                f"users/{login}/repos", {"type": "all"}
            ):
                yield simplify_repo(response)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "user repos",
                    login,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting repos for user %s", login, exc_info=True
                )
