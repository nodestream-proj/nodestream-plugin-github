import logging
from typing import AsyncIterator

from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.repository import (
    SimplifiedRepo,
    simplify_repo,
)
from nodestream_github.interpretations.relationship.user import (
    SimplifiedUser,
    simplify_user,
)
from nodestream_github.util.githubclient import GithubRestApiClient
from nodestream_github.util.types import GithubOrg, GithubOrgSummary, OrgRecord

logger = logging.getLogger(__name__)


class GithubOrganizationsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def _fetch_members(
        self, login: str, role: str
    ) -> AsyncIterator[SimplifiedUser]:
        try:
            async for member in self.client.get(
                f"orgs/{login}/members", {"role": role}
            ):
                yield simplify_user(member) | {"role": role}
        except HTTPStatusError as e:
            logger.debug("Problem getting org members for '%s': %s", login, e)
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
            login = org["login"]
            try:
                yield await self._extract_organization(login)
            except HTTPStatusError as e:
                logger.debug("Problem getting full-org info for '%s': %s", login, e)
            except HTTPError as e:
                logger.warning(
                    "Major problem getting full-org info for '%s' (%s): %s",
                    login,
                    e.request.url,
                    e,
                )

    async def _extract_organization(self, login) -> OrgRecord:
        full_org_info = await self._fetch_full_org(login)
        full_org_info["members"] = [
            member async for member in self._fetch_all_members(login)
        ]

        full_org_info["repositories"] = [
            repo async for repo in self._fetch_repos(login)
        ]

        return full_org_info

    async def _fetch_full_org(self, login: str) -> GithubOrg:
        logger.debug(f"fetching full org={login}")
        return await self.client.get_item(f"orgs/{login}")

    async def _fetch_all_members(self, login) -> AsyncIterator[SimplifiedUser]:
        async for admin in self._fetch_members(login, "admin"):
            yield admin

        async for member in self._fetch_members(login, "member"):
            yield member

    async def _fetch_repos(self, login) -> AsyncIterator[SimplifiedRepo]:
        try:
            async for response in self.client.get(f"orgs/{login}/repos"):
                yield simplify_repo(response)
        except HTTPStatusError as e:
            logger.debug("Problem getting org repos for '%s': %s", login, e)

        except HTTPError as e:
            logger.warning(
                "Major problem getting org repo info for '%s' (%s): %s",
                login,
                e.request.url,
                e,
            )
