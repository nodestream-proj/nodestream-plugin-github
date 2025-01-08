"""
Nodestream Extractor that creates GitHub organization nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from typing import AsyncIterator

import httpx
from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from .interpretations.relationship.repository import simplify_repo
from .interpretations.relationship.user import simplify_user
from .types import (
    GithubOrg,
    GithubOrgSummary,
    OrgRecord,
    SimplifiedRepo,
    SimplifiedUser,
)
from .util import GithubRestApiClient, init_logger
from .util.permissions import PermissionCategory, PermissionName

logger = init_logger(__name__)


class GithubOrganizationsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def _fetch_members(
        self, login: str, role: str
    ) -> AsyncIterator[SimplifiedUser]:
        """Fetch all users who are members of an organization.

        If the authenticated user is also a member of this organization then both
        concealed and public members will be returned.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/members?apiVersion=2022-11-28#list-organization-members

        Fine-grained access tokens require the "Members" organization permissions (read)
        """
        try:
            async for member in self.client.get(
                f"orgs/{login}/members", {"role": role}
            ):
                yield simplify_user(member) | {"role": role}
        except HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "org members",
                    login,
                    PermissionName.MEMBERS,
                    PermissionCategory.ORG,
                    exc_info=True,
                )
            else:
                logger.warning("Problem getting org members for '%s': %s", login, e)
        except HTTPError as e:
            logger.warning(
                "Major problem getting org membership info for '%s' (%s): %s",
                login,
                e.request.url,
                e,
            )

    async def _fetch_all_organizations(self) -> AsyncIterator[GithubOrgSummary]:
        async for org in self.client.get("organizations"):
            yield org

    async def extract_records(self) -> AsyncIterator[OrgRecord]:
        async for org in self._fetch_all_organizations():
            enhanced_org = await self._extract_organization(org["login"])
            if enhanced_org:
                yield enhanced_org

    async def _extract_organization(self, login) -> OrgRecord | None:
        full_org = await self._fetch_full_org(login)
        if not full_org:
            return None

        full_org["members"] = [user async for user in self._fetch_all_members(login)]

        full_org["repositories"] = [repo async for repo in self._fetch_repos(login)]
        return full_org

    async def _fetch_full_org(self, login: str) -> GithubOrg:
        """Fetches the complete org record.

        https://docs.github.com/en/enterprise-server@3.12/rest/orgs/orgs?apiVersion=2022-11-28#get-an-organization

        Personal access tokens (classic) need the admin:org scope to see the
        full details about an organization.

        The fine-grained token does not require any permissions.
        """
        try:
            logger.debug(f"fetching full org={login}")
            return await self.client.get_item(f"orgs/{login}")
        except HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.warning(
                    "Current access token does not have permissions to get org details for %s",
                    login,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting full-org info for '%s'",
                    login,
                    exc_info=True,
                )

        except HTTPError:
            logger.warning(
                "Major problem getting full-org info for '%s'",
                login,
                exc_info=True,
            )

    async def _fetch_all_members(self, login) -> AsyncIterator[SimplifiedUser]:
        async for admin in self._fetch_members(login, "admin"):
            yield admin

        async for member in self._fetch_members(login, "member"):
            yield member

    async def _fetch_repos(self, login) -> AsyncIterator[SimplifiedRepo]:
        """Fetches repositories for the specified organization.

        Note: In order to see the security_and_analysis block for a repository you
        must have admin permissions for the repository or be an owner or security
        manager for the organization that owns the repository.

        https://docs.github.com/en/enterprise-server@3.12/rest/repos/repos?apiVersion=2022-11-28#list-organization-repositories

        If using a fine-grained access token, the token must have the "Metadata"
        repository permissions (read)
        """
        try:
            async for response in self.client.get(f"orgs/{login}/repos"):
                yield simplify_repo(response)
        except HTTPStatusError as e:
            if e.response.status_code == 403:
                logger.permission_warning(
                    "org repos",
                    login,
                    PermissionName.METADATA,
                    PermissionCategory.REPO,
                    exc_info=True,
                )
            else:
                logger.warning("Problem getting org repos for '%s': %s", login, e)

        except HTTPError as e:
            logger.warning(
                "Major problem getting org repo info for '%s' (%s): %s",
                login,
                e.request.url,
                e,
            )
