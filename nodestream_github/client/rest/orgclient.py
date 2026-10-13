from collections.abc import AsyncGenerator
from typing import cast

import httpx2

from nodestream_github.client.rest import GithubRestApiClient, log_fetch_problem
from nodestream_github.client.rest.githubclient import has_required_keys
from nodestream_github.logging import get_plugin_logger
from nodestream_github.types.enums import OrgRepoType
from nodestream_github.types.gh_model import (
    MinimalRepository,
    NullableSimpleUser,
    OrganizationFull,
    OrganizationSimple,
    OrgMembershipRole,
)

logger = get_plugin_logger(__name__)


class OrgClient:
    def __init__(self, client: GithubRestApiClient):
        self.client: GithubRestApiClient = client

    async def fetch_repos_for_org(
        self,
        *,
        org_login: str,
        repo_type: OrgRepoType | None = None,
    ) -> AsyncGenerator[MinimalRepository]:
        """Fetches repositories for the specified organization.

        Note: In order to see the security_and_analysis block for a repository you
        must have admin permissions for the repository or be an owner or security
        manager for the organization that owns the repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-organization-repositories

        If using a fine-grained access token, the token must have the "Metadata"
        repository permissions (read)
        """
        try:
            params = {}
            if repo_type:
                params["type"] = repo_type
            async for response in self.client.get_paginated(
                f"orgs/{org_login}/repos", params=params
            ):
                if has_required_keys("repo", response, MinimalRepository):
                    yield cast("MinimalRepository", response)

        except httpx2.HTTPError as e:
            log_fetch_problem(f"repos for org {org_login}", e)

    async def fetch_members_for_org(
        self,
        *,
        org_login: str,
        role: OrgMembershipRole | None = None,
    ) -> AsyncGenerator[NullableSimpleUser]:
        """Fetch all users who are members of an organization.

        If the authenticated user is also a member of this organization then both
        concealed and public members will be returned.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/members?apiVersion=2022-11-28#list-organization-members

        Fine-grained access tokens require the "Members" organization permissions (read)
        """
        try:
            params = {}
            if role:
                params["role"] = role
            async for member in self.client.get_paginated(
                f"orgs/{org_login}/members", params=params
            ):
                if has_required_keys("member", member, NullableSimpleUser):
                    yield cast("NullableSimpleUser", member)

        except httpx2.HTTPError as e:
            log_fetch_problem(f"members for org {org_login}", e)

    async def fetch_all_organizations(self) -> AsyncGenerator[OrganizationSimple]:
        """Fetches all organizations, in the order that they were created.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#list-organizations
        """
        try:
            async for org in self.client.get_paginated("organizations"):
                yield OrganizationSimple(**org)
        except httpx2.HTTPError as e:
            log_fetch_problem("all organizations", e)

    async def fetch_full_org(self, org_login: str) -> OrganizationFull | None:
        """Fetches the complete org record.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#get-an-organization

        Personal access tokens (classic) need the admin:org scope to see the
        full details about an organization.

        The fine-grained token does not require any permissions.
        """
        try:
            logger.debug("fetching full org=%s", org_login)
            item = await self.client.get_item(f"orgs/{org_login}")
            return OrganizationFull(**item)
        except httpx2.HTTPError as e:
            log_fetch_problem(f"full organization info for {org_login}", e)
            return None
