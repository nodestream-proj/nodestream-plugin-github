import logging
from typing import Any, AsyncGenerator

from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.util.githubclient import GithubRestApiClient
from nodestream_github.util.simplify import simplify_repo, simplify_user

logger = logging.getLogger(__name__)


class GithubOrganizationsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncGenerator[Any, Any]:
        async for page in self.client.get("organizations"):
            login = page["login"]
            try:
                full_org_info = await self._extract_organization(login)
                yield full_org_info
            except HTTPStatusError as e:
                logger.debug("Problem getting full-org info for '%s': %s", login, e)
            except HTTPError as e:
                logger.warning(
                    "Major problem getting full-org info for '%s' (%s): %s",
                    login,
                    e.request.url,
                    e,
                )

    async def _fetch_members(self, login, role):
        async for response in self.client.get(f"orgs/{login}/members", {"role": role}):
            yield simplify_user(response)

    async def _extract_organization(self, login):
        logger.debug(f"fetching org={login}")
        full_org_info = await self.client.get_item(f"orgs/{login}")
        full_org_info["members"] = []
        try:
            async for response in self._fetch_members(login, "admin"):
                response["role"] = "admin"
                full_org_info["members"].append(response)
            async for response in self._fetch_members(login, "member"):
                response["role"] = "member"
                full_org_info["members"].append(response)
        except HTTPStatusError as e:
            logger.debug("Problem getting org members for '%s': %s", login, e)
        except HTTPError as e:
            logger.warning(
                "Major problem getting org membership info for '%s' (%s): %s",
                login,
                e.request.url,
                e,
            )

        try:
            full_org_info["repositories"] = [
                simplify_repo(response)
                async for response in self.client.get(f"orgs/{login}/repos")
            ]
        except HTTPStatusError as e:
            logger.debug("Problem getting org repos for '%s': %s", login, e)
            full_org_info["repositories"] = []
        except HTTPError as e:
            logger.warning(
                "Major problem getting org repo info for '%s' (%s): %s",
                login,
                e.request.url,
                e,
            )
            full_org_info["repositories"] = []

        return full_org_info
