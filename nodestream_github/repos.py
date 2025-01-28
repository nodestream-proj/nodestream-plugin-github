"""
Nodestream Extractor that creates GitHub repository nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass

from nodestream.pipeline import Extractor

from .client import GithubRestApiClient
from .interpretations.relationship.user import simplify_user
from .logging import get_plugin_logger
from .types import GithubRepo, RepositoryRecord

logger = get_plugin_logger(__name__)


def _dict_val_to_bool(d: dict[str, any], key: str) -> bool:
    value = d.get(key)
    if value is None:
        return False
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

    @staticmethod
    def from_dict(raw_dict: dict[str, any]) -> "CollectWhichRepos":
        org_all = _dict_val_to_bool(raw_dict, "org_all")
        user_all = _dict_val_to_bool(raw_dict, "user_all")

        return CollectWhichRepos(
            all_public=_dict_val_to_bool(raw_dict, "all_public"),
            org_public=org_all or _dict_val_to_bool(raw_dict, "org_public"),
            org_private=org_all or _dict_val_to_bool(raw_dict, "org_private"),
            user_public=user_all or _dict_val_to_bool(raw_dict, "user_public"),
            user_private=user_all or _dict_val_to_bool(raw_dict, "user_private"),
        )


class GithubReposExtractor(Extractor):
    def __init__(
        self,
        collecting: CollectWhichRepos | dict[str, any] | None = None,
        **kwargs: any,
    ):
        if isinstance(collecting, CollectWhichRepos):
            self.collecting = collecting
        elif isinstance(collecting, dict):
            self.collecting = CollectWhichRepos.from_dict(collecting)
        else:
            self.collecting = CollectWhichRepos()
        self.client = GithubRestApiClient(**kwargs)

    async def extract_records(self) -> AsyncGenerator[RepositoryRecord]:
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
        logger.debug("yielded GithubRepo{full_name=%s}", repo["full_name"])
        return repo

    async def _fetch_repos_by_org(self) -> AsyncGenerator[GithubRepo]:
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

    async def _fetch_repos_by_user(self) -> AsyncGenerator[GithubRepo]:
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
