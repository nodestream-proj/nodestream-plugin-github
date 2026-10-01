from collections.abc import AsyncGenerator
from typing import cast

import httpx

from nodestream_github.client.rest.githubclient import (
    GithubRestApiClient,
    log_fetch_problem,
)
from nodestream_github.logging import get_plugin_logger
from nodestream_github.types import enums
from nodestream_github.types.gh_model import (
    BranchProtection,
    Collaborator,
    Hook,
    Language,
    MinimalRepository,
)

logger = get_plugin_logger(__name__)


class RepoClient:
    def __init__(self, client: GithubRestApiClient):
        self.client: GithubRestApiClient = client

    async def fetch_languages_for_repo(
        self,
        *,
        owner_login: str,
        repo_name: str,
    ) -> Language:
        """Fetch languages for the specified repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repository-languages

        Fine-grained access tokens require the "Metadata" repository permissions (read).
        """
        try:
            lang_resp = await self.client.get_item(
                f"repos/{owner_login}/{repo_name}/languages"
            )
            if lang_resp:
                return cast("dict[str, int]", lang_resp)

        except httpx.HTTPError as e:
            log_fetch_problem(f"languages for repo {owner_login}/{repo_name}", e)
        return {}

    async def fetch_webhooks_for_repo(
        self,
        *,
        owner_login: str,
        repo_name: str,
    ) -> AsyncGenerator[Hook]:
        """Try to get types.webhook data for this repo.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/webhooks?apiVersion=2022-11-28#list-repository-webhooks

        Fine-grained access tokens require the "Webhooks" repository permissions (read).
        """
        try:
            async for hook in self.client.get_paginated(
                f"repos/{owner_login}/{repo_name}/hooks"
            ):
                yield Hook(**hook)

        except httpx.HTTPError as e:
            log_fetch_problem(f"webhooks for repo {owner_login}/{repo_name}", e)

    async def fetch_collaborators_for_repo(
        self,
        *,
        owner_login: str,
        repo_name: str,
        affiliation: enums.CollaboratorAffiliation,
    ) -> AsyncGenerator[Collaborator]:
        """Try to get collaborator data for this repo.

        For organization-owned repositories, the list of collaborators includes
        outside collaborators, organization members that are direct collaborators,
        organization members with access through team memberships, organization
        members with access through default organization permissions,
        and organization owners. Organization members with write, maintain, or admin
        privileges on the organization-owned repository can use this endpoint.

        https://docs.github.com/en/enterprise-server@3.12/rest/collaborators/collaborators?apiVersion=2022-11-28

        The authenticated user must have push access to the repository to use
        this endpoint.

        OAuth app tokens and personal access tokens (classic) need the `read:org`
        and `repo` scopes to use this endpoint.

        Fine-grained access tokens require the "Metadata" repository permissions (read)
        """
        try:
            async for collab_resp in self.client.get_paginated(
                f"repos/{owner_login}/{repo_name}/collaborators",
                params={"affiliation": affiliation},
            ):
                yield Collaborator(**collab_resp)

        except httpx.HTTPError as e:
            log_fetch_problem(f"collaborators for repo {owner_login}/{repo_name}", e)

    async def fetch_all_public_repos(self) -> AsyncGenerator[MinimalRepository]:
        """
        Returns all public repositories in the order that they were created.

        Note:
            - For GitHub Enterprise Server, this endpoint will only list repositories
                available to all users on the enterprise.
            - Pagination is powered exclusively by the 'since' parameter. Use the
                Link header to get the URL for the next page of repositories.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-public-repositories

        If using a fine-grained access token, the token must have the
        "Metadata" repository permissions (read)
        """
        try:
            async for repo in self.client.get_paginated("repositories"):
                yield MinimalRepository(**repo)

        except httpx.HTTPError as e:
            log_fetch_problem("all public repositories", e)

    async def fetch_teams_for_repo(self, *, owner_login: str, repo_name: str):
        """
        Lists the teams that have access to the specified repository and that
        are also visible to the authenticated user.

        For a public repository, a team is listed only if that team added the
        public repository explicitly.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-repository-teams
        """
        try:
            async for team in self.client.get_paginated(
                f"repos/{owner_login}/{repo_name}/teams"
            ):
                yield team
        except httpx.HTTPError as e:
            log_fetch_problem(f"teams for repo {owner_login}/{repo_name}", e)

    async def fetch_branch_protection(
        self,
        *,
        owner_login: str,
        repo_name: str,
        branch: str,
    ) -> BranchProtection | None:
        """Fetches the branch protection for a given branch.

        https://docs.github.com/en/enterprise-server@3.12/rest/branches/branch-protection?apiVersion=2022-11-28#get-branch-protection
        """

        try:
            item = await self.client.get_item(
                f"repos/{owner_login}/{repo_name}/branches/{branch}/protection"
            )
            return BranchProtection(**item) if item else None
        except httpx.HTTPError as e:
            match e:
                case httpx.HTTPStatusError(response=response) if (
                    response.status_code == 404
                ):
                    logger.info(
                        "Branch protection not found for branch %s on repo %s/%s",
                        branch,
                        owner_login,
                        repo_name,
                    )
                case _:
                    log_fetch_problem(
                        f"branch protection for branch {branch} on "
                        f"repo {owner_login}/{repo_name}",
                        e,
                    )
            return None
