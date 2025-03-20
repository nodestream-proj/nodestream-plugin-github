"""
Nodestream Extractor that creates GitHub user nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator
from typing import Any

from nodestream.pipeline import Extractor

from .client import GithubRestApiClient
from .interpretations.relationship.repository import simplify_repo
from .logging import get_plugin_logger
from .types import UserRecord
from .types.enums import UserRepoType

logger = get_plugin_logger(__name__)


class GithubUserExtractor(Extractor):
    def __init__(self, **github_client_kwargs: Any):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncGenerator[UserRecord]:
        """Scrapes the GitHub REST api for all users and converts them to records."""
        async for user in self.client.fetch_all_users():
            login = user["login"]
            user["repositories"] = [
                simplify_repo(repo)
                async for repo in self.client.fetch_repos_for_user(
                    user_login=login,
                    repo_type=UserRepoType.OWNER,
                )
            ]
            logger.debug("yielded GithubUser{login=%s}", login)
            yield user
