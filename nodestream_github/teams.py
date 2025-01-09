"""
Nodestream Extractor that creates GitHub team nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from typing import AsyncIterator

from nodestream.pipeline import Extractor

from .interpretations.relationship.repository import simplify_repo
from .interpretations.relationship.user import simplify_user
from .types import GithubTeam, GithubTeamSummary, SimplifiedUser, TeamRecord
from .util import GithubRestApiClient, init_logger

logger = init_logger(__name__)


class GithubTeamsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[TeamRecord]:
        async for page in self.client.fetch_all_organizations():
            login = page["login"]
            async for team in self.client.fetch_teams_for_org(login):
                team_record = await self._fetch_team(login, team)
                if team_record:
                    yield team_record

    async def _fetch_members(self, team: GithubTeam) -> AsyncIterator[SimplifiedUser]:
        logger.debug(
            "Getting members for team %s/%s",
            team["organization"]["login"],
            team["slug"],
        )

        async for member in self.client.fetch_members_for_team(team["id"], "member"):
            yield member | {"role": "member"}
        async for member in self.client.fetch_members_for_team(
            team["id"], "maintainer"
        ):
            yield member | {"role": "maintainer"}

    async def _fetch_team(
        self, login: str, team_summary: GithubTeamSummary
    ) -> GithubTeam:
        team = await self.client.fetch_team(login, team_summary["slug"])
        if not team:
            return None
        team["members"] = [
            simplify_user(member) async for member in self._fetch_members(team)
        ]
        team["repos"] = [
            simplify_repo(repo)
            async for repo in self.client.fetch_repos_for_team(login, team["slug"])
        ]
        return team
