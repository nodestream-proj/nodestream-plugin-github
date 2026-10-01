"""
Nodestream Extractor that creates GitHub repository nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator
from dataclasses import dataclass
from typing import Any, Self, Unpack

from nodestream.pipeline import Extractor

from nodestream_github.client.rest.githubclient import GithubRestApiClientParams
from nodestream_github.types.gh_model import (
    FullRepository,
    Hook,
    MinimalRepository,
    NullableSimpleUser,
)

from .client import GithubRestApiClient
from .client.rest import OrgClient, RepoClient, UserClient
from .interpretations.relationship.user import simplify_user
from .logging import get_plugin_logger
from .types.enums import CollaboratorAffiliation, OrgRepoType, UserRepoType

logger = get_plugin_logger(__name__)


def _dict_val_to_bool(d: dict[str, Any], key: str) -> bool:
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

    @classmethod
    def from_dict(cls, raw_dict: dict[str, Any]) -> Self:
        org_all = _dict_val_to_bool(raw_dict, "org_all")
        user_all = _dict_val_to_bool(raw_dict, "user_all")

        return cls(
            all_public=_dict_val_to_bool(raw_dict, "all_public"),
            org_public=org_all or _dict_val_to_bool(raw_dict, "org_public"),
            org_private=org_all or _dict_val_to_bool(raw_dict, "org_private"),
            user_public=user_all or _dict_val_to_bool(raw_dict, "user_public"),
            user_private=user_all or _dict_val_to_bool(raw_dict, "user_private"),
        )


class GithubReposExtractor(Extractor):
    def __init__(
        self,
        *,
        collecting: CollectWhichRepos | dict[str, Any] | None = None,
        include_languages: bool | None = True,
        include_webhooks: bool | None = True,
        include_collaborators: bool | None = True,
        **kwargs: Unpack[GithubRestApiClientParams],
    ):
        if isinstance(collecting, CollectWhichRepos):
            self.collecting = collecting
        elif isinstance(collecting, dict):
            self.collecting = CollectWhichRepos.from_dict(collecting)
        else:
            self.collecting = CollectWhichRepos()

        self.include_languages = include_languages is True
        self.include_webhooks = include_webhooks is True
        self.include_collaborators = include_collaborators is True

        self.core_client = GithubRestApiClient(**kwargs)
        self.repo_client = RepoClient(self.core_client)
        self.org_client = OrgClient(self.core_client)
        self.user_client = UserClient(self.core_client)
        logger.info(
            "%s, %s, %s",
            self.include_collaborators,
            self.include_webhooks,
            self.include_languages,
        )

    async def extract_records(self) -> AsyncGenerator[dict[str, Any]]:
        if self.collecting.all_public:
            async for repo in self.repo_client.fetch_all_public_repos():
                yield await self._extract_repo(repo)

        if self.collecting.org_any:
            async for repo in self._fetch_repos_by_org():
                yield await self._extract_repo(repo)

        if self.collecting.user_any:
            async for repo in self._fetch_repos_by_user():
                yield await self._extract_repo(repo)

    async def _extract_repo(
        self,
        repo: FullRepository | MinimalRepository,
    ) -> dict[str, Any]:
        output = {**repo}
        owner = repo["owner"]
        del output["owner"]
        if owner["type"] == "User":
            output["user_owner"] = owner
        elif owner:
            output["org_owner"] = owner

        if self.include_languages:
            output["languages"] = await self._add_languages(owner, repo)
        if self.include_webhooks:
            output["webhooks"] = await self._add_webhooks(owner, repo)
        if self.include_collaborators:
            output["collaborators"] = await self._add_collaborators(owner, repo)

        logger.debug("yielded GithubRepo{full_name=%s}", repo["full_name"])
        return output

    async def _add_collaborators(
        self,
        owner: NullableSimpleUser,
        repo: FullRepository | MinimalRepository,
    ) -> list[dict[str, Any]]:
        collaborators = [
            simplify_user(user) | {"affiliation": "direct"}
            async for user in self.repo_client.fetch_collaborators_for_repo(
                owner_login=owner["login"],
                repo_name=repo["name"],
                affiliation=CollaboratorAffiliation.DIRECT,
            )
        ]
        collaborators.extend([
            simplify_user(user) | {"affiliation": "outside"}
            async for user in self.repo_client.fetch_collaborators_for_repo(
                owner_login=owner["login"],
                repo_name=repo["name"],
                affiliation=CollaboratorAffiliation.OUTSIDE,
            )
        ])

        return collaborators

    async def _add_webhooks(
        self,
        owner: NullableSimpleUser,
        repo: FullRepository | MinimalRepository,
    ) -> list[Hook]:
        return [
            hook
            async for hook in self.repo_client.fetch_webhooks_for_repo(
                owner_login=owner["login"],
                repo_name=repo["name"],
            )
        ]

    async def _add_languages(
        self,
        owner: NullableSimpleUser,
        repo: FullRepository | MinimalRepository,
    ) -> list[dict[str, str]]:
        languages = await self.repo_client.fetch_languages_for_repo(
            owner_login=owner["login"],
            repo_name=repo["name"],
        )
        return [{"name": lang} for lang in languages]

    async def _fetch_repos_by_org(self) -> AsyncGenerator[MinimalRepository]:
        async for org in self.org_client.fetch_all_organizations():
            if self.collecting.org_public:
                async for repo in self.org_client.fetch_repos_for_org(
                    org_login=org["login"],
                    repo_type=OrgRepoType.PUBLIC,
                ):
                    yield repo
            if self.collecting.org_private:
                async for repo in self.org_client.fetch_repos_for_org(
                    org_login=org["login"],
                    repo_type=OrgRepoType.PRIVATE,
                ):
                    yield repo

    async def _fetch_repos_by_user(self) -> AsyncGenerator[MinimalRepository]:
        """Fetches repositories for the specified user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        If using a fine-grained access token, the token must have the "Metadata"
        repository permissions (read)
        """
        async for user in self.user_client.fetch_all_users():
            async for repo in self.user_client.fetch_repos_for_user(
                user_login=user["login"],
                repo_type=UserRepoType.OWNER,
            ):
                yield repo
