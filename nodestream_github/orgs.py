"""
Nodestream Extractor that creates GitHub organization nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from typing import AsyncIterator

from nodestream.pipeline import Extractor

from .interpretations.relationship.repository import simplify_repo
from .interpretations.relationship.user import simplify_user
from .types import OrgRecord, SimplifiedUser
from .util import GithubRestApiClient, init_logger

logger = init_logger(__name__)


class GithubOrganizationsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[OrgRecord]:
        async for org in self.client.fetch_all_organizations():
            enhanced_org = await self._extract_organization(org["login"])
            if enhanced_org:
                yield enhanced_org

    async def _extract_organization(self, login) -> OrgRecord | None:
        full_org = await self.client.fetch_full_org(login)
        if not full_org:
            return None

        full_org["members"] = [user async for user in self._fetch_all_members(login)]

        full_org["repositories"] = [
            simplify_repo(repo) async for repo in self.client.fetch_repos_for_org(login)
        ]
        return full_org

    async def _fetch_all_members(self, login) -> AsyncIterator[SimplifiedUser]:
        async for admin in self.client.fetch_members_for_org(login, "admin"):
            yield simplify_user(admin) | {"role": "admin"}

        async for member in self.client.fetch_members_for_org(login, "member"):
            yield simplify_user(member) | {"role": "member"}
