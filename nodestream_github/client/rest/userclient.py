from collections.abc import AsyncGenerator
from typing import cast

import httpx2

from nodestream_github.client.rest.githubclient import (
    GithubRestApiClient,
    has_required_keys,
    log_fetch_problem,
)
from nodestream_github.types import enums
from nodestream_github.types.gh_model import (
    MinimalRepository,
    NullableSimpleUser,
    PrivateUser,
)


class UserClient:
    def __init__(self, client: GithubRestApiClient):
        self.client: GithubRestApiClient = client

    async def fetch_all_users(self) -> AsyncGenerator[NullableSimpleUser]:
        """
        Fetches all users in the order that they were created.

        https://docs.github.com/en/enterprise-server@3.12/rest/users/users?apiVersion=2022-11-28#list-users
        """
        try:
            async for user in self.client.get_paginated("users"):
                if (
                    has_required_keys("user", user, NullableSimpleUser)
                    and user["type"] == "User"
                ):
                    yield cast("NullableSimpleUser", user)
        except httpx2.HTTPError as e:
            log_fetch_problem("all users", e)

    async def fetch_user(self, *, username: str) -> PrivateUser | None:
        """
        Provides publicly available information about someone with a GitHub account.

        https://docs.github.com/en/enterprise-server@3.12/rest/users/users?apiVersion=2022-11-28#get-a-user
        """
        try:
            return PrivateUser(**await self.client.get_item(f"users/{username}"))
        except httpx2.HTTPError as e:
            log_fetch_problem(f"full user info for {username}", e)
            return None

    async def fetch_repos_for_user(
        self,
        *,
        user_login: str,
        repo_type: enums.UserRepoType | None = None,
    ) -> AsyncGenerator[MinimalRepository]:
        """Fetches repositories for a user.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repositories-for-a-user

        Fine-grained token must have the "Metadata" repository permissions (read)
        """
        try:
            params = {}
            if repo_type:
                params["type"] = repo_type
            async for repo in self.client.get_paginated(
                f"users/{user_login}/repos", params=params
            ):
                if has_required_keys("repo", repo, MinimalRepository):
                    yield cast("MinimalRepository", repo)

        except httpx2.HTTPError as e:
            log_fetch_problem(f"repos for user {user_login}", e)
