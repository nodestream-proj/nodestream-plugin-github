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
from .types import SimplifiedUser, UserRecord
from .types.enums import UserRepoType

logger = get_plugin_logger(__name__)


class GithubUserExtractor(Extractor):
    def __init__(self, *, include_repos: bool = True, **github_client_kwargs: Any):
        self.include_repos = include_repos is True  # handle None
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncGenerator[UserRecord]:
        """Scrapes the GitHub REST api for all users and converts them to records."""
        async for user_short in self.client.fetch_all_users():
            login = user_short["login"]
            user = await self.client.fetch_user(username=login)
            if user is None:
                continue
            if self.include_repos:
                logger.debug("including repos for %s", user)
                user["repositories"] = await self._user_repos(login=login)
            logger.debug("yielded GithubUser{login=%s}", login)
            yield user

    async def _user_repos(self, *, login: str) -> list[SimplifiedUser]:
        return [
            simplify_repo(repo)
            async for repo in self.client.fetch_repos_for_user(
                user_login=login,
                repo_type=UserRepoType.OWNER,
            )
        ]
