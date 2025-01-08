from typing import AsyncIterator

from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from .interpretations.relationship.repository import simplify_repo
from .interpretations.relationship.user import simplify_user
from .types import (
    GithubTeam,
    GithubTeamSummary,
    SimplifiedRepo,
    SimplifiedUser,
    TeamRecord,
)
from .util import GithubRestApiClient, init_logger

logger = init_logger(__name__)


class GithubTeamsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[TeamRecord]:
        async for page in self.client.get("organizations"):
            login = page["login"]
            async for team in self._fetch_teams(login):
                yield team

    async def _fetch_members_by_role(
        self, team: GithubTeam, role: str
    ) -> AsyncIterator[SimplifiedUser]:
        try:
            async for member in self.client.get(
                f"teams/{team["id"]}/members", {"role": role}
            ):
                yield simplify_user(member) | {"role": role}
        except HTTPStatusError:
            logger.warning(
                "Problem getting %s members for team '%s/%s'",
                role,
                team["organization"]["login"],
                team["id"],
                exc_info=True,
            )

    async def _fetch_members(self, team: GithubTeam) -> AsyncIterator[SimplifiedUser]:
        logger.debug(
            "Getting members for team %s/%s",
            team["organization"]["login"],
            team["slug"],
        )

        async for member in self._fetch_members_by_role(team, "member"):
            yield member
        async for member in self._fetch_members_by_role(team, "maintainer"):
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

    async def _fetch_repos(self, team: GithubTeam) -> AsyncIterator[SimplifiedRepo]:
        try:
            async for repo in self.client.get(f"teams/{team["id"]}/repos"):
                yield simplify_repo(repo)
        except HTTPStatusError:
            logger.warning(
                "Problem getting repos for team '%s/%s': %s",
                team["organization"]["login"],
                team["slug"],
                exc_info=True,
            )

    async def _fetch_team(
        self, login: str, team_summary: GithubTeamSummary
    ) -> GithubTeam:
        team = await self.client.get_item(f"orgs/{login}/teams/{team_summary['slug']}")
        team["members"] = [member async for member in self._fetch_members(team)]
        team["repos"] = [repo async for repo in self._fetch_repos(team)]
        return team
