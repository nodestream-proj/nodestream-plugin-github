import logging
from typing import AsyncIterator

from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.interpretations.relationship.user import simplify_user
from nodestream_github.util.githubclient import GithubRestApiClient
from nodestream_github.util.types import (
    GithubTeam,
    GithubTeamSummary,
    SimplifiedRepo,
    SimplifiedUser,
    TeamRecord,
)

logger = logging.getLogger(__name__)


class GithubTeamsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[TeamRecord]:
        async for page in self.client.get("organizations"):
            login = page["login"]
            async for team in self._fetch_teams(login):
                yield team

    async def _fetch_members_by_role(
        self, login: str, slug: str, role: str
    ) -> AsyncIterator[SimplifiedUser]:
        try:
            async for member in self.client.get(
                f"orgs/{login}/teams/{slug}/members", {"role": role}
            ):
                yield simplify_user(member) | {"role": role}
        except HTTPStatusError as e:
            logger.warning(
                "Problem getting %s members for team '%s/%s': %s", role, login, slug, e
            )

    async def _fetch_members(
        self, login: str, slug: str
    ) -> AsyncIterator[SimplifiedUser]:
        logger.debug("Getting members for team %s/%s", login, slug)

        async for member in self._fetch_members_by_role(login, slug, "member"):
            yield member
        async for member in self._fetch_members_by_role(login, slug, "maintainer"):
            yield member

    async def _fetch_teams(self, login):
        try:
            logger.debug("Getting teams for %s", login)
            async for team_summary in self.client.get(
                f"orgs/{login}/teams",
            ):
                yield await self._fetch_team(login, team_summary)
        except HTTPStatusError as e:
            logger.debug("Problem getting team info for org '%s': %s", login, e)
        except HTTPError as e:
            logger.warning("Major problem getting team info for org '%s': %s", login, e)

    async def _fetch_repos(
        self, login: str, slug: str
    ) -> AsyncIterator[SimplifiedRepo]:
        try:
            async for repo in self.client.get(f"orgs/{login}/teams/{slug}/repos"):
                yield simplify_repo(repo)
        except HTTPStatusError as e:
            logger.warning("Problem getting repos for team '%s/%s': %s", login, slug, e)

    async def _fetch_team(
        self, login: str, team_summary: GithubTeamSummary
    ) -> GithubTeam:
        team = await self.client.get_item(f"orgs/{login}/teams/{team_summary['slug']}")
        team["members"] = [
            member async for member in self._fetch_members(login, team["slug"])
        ]
        team["repos"] = [repo async for repo in self._fetch_repos(login, team["slug"])]
        return team
