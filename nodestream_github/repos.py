"""
Nodestream Extractor that creates GitHub repository nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from dataclasses import dataclass
from typing import AsyncIterator

from nodestream.pipeline import Extractor

from .interpretations.relationship.user import simplify_user
from .types import GithubRepo, RepositoryRecord
from .util import GithubRestApiClient, init_logger

logger = init_logger(__name__)


def _dict_val_to_bool(d: dict[str, any], key: str, default: bool = False) -> bool:
    value = d.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value

    return True  # key is present


@dataclass
class CollectWhichRepos:
    all_public: bool = False
    org_public: bool = False
    org_private: bool = False
    user_public: bool = False
    user_private: bool = False

    @property
    def org_any(self) -> bool:
        return self.org_public or self.org_private

    @property
    def user_any(self) -> bool:
        return self.user_public or self.user_private

    @classmethod
    def from_dict(cls, raw_input: dict[str, any]):
        org_all = _dict_val_to_bool(raw_input, "org_all", False)
        user_all = _dict_val_to_bool(raw_input, "user_all", False)

        return CollectWhichRepos(
            all_public=_dict_val_to_bool(raw_input, "all_public", False),
            org_public=org_all | _dict_val_to_bool(raw_input, "org_public", False),
            org_private=org_all | _dict_val_to_bool(raw_input, "org_private", False),
            user_public=user_all | _dict_val_to_bool(raw_input, "user_public", False),
            user_private=user_all | _dict_val_to_bool(raw_input, "user_private", False),
        )


class GithubReposExtractor(Extractor):
    def __init__(
        self,
        collecting: CollectWhichRepos | dict[str, any] | None = None,
        **kwargs,
    ):
        if isinstance(collecting, CollectWhichRepos):
            self.collecting = collecting
        elif isinstance(collecting, dict):
            self.collecting = CollectWhichRepos.from_dict(collecting)
        else:
            self.collecting = CollectWhichRepos()
        self.client = GithubRestApiClient(**kwargs)

    async def extract_records(self) -> AsyncIterator[RepositoryRecord]:
        if self.collecting.all_public:
            async for repo in self.client.fetch_all_public_repos():
                yield await self._extract_repo(repo)

        if self.collecting.org_any:
            async for repo in self._fetch_repos_by_org():
                yield await self._extract_repo(repo)

        if self.collecting.user_any:
            async for repo in self._fetch_repos_by_user():
                yield await self._extract_repo(repo)

    async def _extract_repo(self, repo: GithubRepo) -> RepositoryRecord:
        """Enhances raw GitHub json data into a dict that supports using it in pipelines."""
        owner = repo.pop("owner", {})
        if owner.get("type") == "User":
            repo["user_owner"] = owner
        elif owner:
            repo["org_owner"] = owner
        repo["languages"] = [
            {"name": lang}
            async for lang in self.client.fetch_languages_for_repo(
                owner["login"], repo["name"]
            )
        ]
        logger.info("owner=%s", owner)
        repo["webhooks"] = [
            hook
            async for hook in self.client.fetch_webhooks_for_repo(
                owner["login"], repo["name"]
            )
        ]
        repo["collaborators"] = [
            simplify_user(user)
            async for user in self.client.fetch_collaborators_for_repo(
                owner["login"], repo["name"]
            )
        ]
        return repo

    async def _fetch_repos_by_org(self) -> AsyncIterator[GithubRepo]:
        async for org in self.client.fetch_all_organizations():
            if self.collecting.org_public:
                async for repo in self.client.fetch_repos_for_org(
                    org["login"], "public"
                ):
                    yield repo
            if self.collecting.org_private:
                async for repo in self.client.fetch_repos_for_org(
                    org["login"], "private"
                ):
                    yield repo

    async def _fetch_repos_by_user(self) -> AsyncIterator[GithubRepo]:
        """Fetches repositories for the specified user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        If using a fine-grained access token, the token must have the "Metadata"
        repository permissions (read)
        """
        async for user in self.client.fetch_all_users():
            if self.collecting.user_public:
                async for repo in self.client.fetch_repos_for_user(
                    user["login"], "public"
                ):
                    yield repo
            if self.collecting.user_private:
                async for repo in self.client.fetch_repos_for_user(
                    user["login"], "private"
                ):
                    yield repo
