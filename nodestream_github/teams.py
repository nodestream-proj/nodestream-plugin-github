"""
Nodestream Extractor that creates GitHub team nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from typing import AsyncIterator

import httpx
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
from .util import GithubRestApiClient, PermissionCategory, PermissionName, init_logger

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
        """Fetch all users that have a given role for a specified team.

        These endpoints are only available to authenticated members of the
        team's organization.

        Access tokens require the read:org scope.

        To list members in a team, the team must be visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/members?apiVersion=2022-11-28#list-team-members-legacy
        """
        try:
            async for member in self.client.get(
                f"teams/{team["id"]}/members", {"role": role}
            ):
                yield simplify_user(member) | {"role": role}
        except httpx.HTTPError:
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
        """Fetch all teams in an organization that are visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-teams

        Fine-grained tokens must have the "Members" organization permissions (read)
        """
        try:
            logger.debug("Getting teams for %s", login)
            async for team_summary in self.client.get(
                f"orgs/{login}/teams",
            ):
                yield await self._fetch_team(login, team_summary)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == httpx.codes.FORBIDDEN:
                logger.permission_warning(
                    "org teams",
                    login,
                    PermissionName.MEMBERS,
                    PermissionCategory.ORG,
                    exc_info=True,
                )
            else:
                logger.warning(
                    "Problem getting team info for org '%s'", login, exc_info=True
                )
        except httpx.HTTPError:
            logger.warning(
                "Major problem getting team info for org '%s'", login, exc_info=True
            )

    async def _fetch_repos(self, team: GithubTeam) -> AsyncIterator[SimplifiedRepo]:
        """Fetch all repos for a specified team that are visible to the authenticated user.

        These endpoints are only available to authenticated members of the
        team's organization.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-team-repositories
        """
        try:
            async for repo in self.client.get(f"teams/{team["id"]}/repos"):
                yield simplify_repo(repo)
        except httpx.HTTPError:
            logger.warning(
                "Problem getting repos for team '%s/%s'",
                team["organization"]["login"],
                team["id"],
                exc_info=True,
            )

    async def _fetch_team(
        self, login: str, team_summary: GithubTeamSummary
    ) -> GithubTeam:
        team = await self.client.get_item(f"orgs/{login}/teams/{team_summary['slug']}")
        team["members"] = [member async for member in self._fetch_members(team)]
        team["repos"] = [repo async for repo in self._fetch_repos(team)]
        return team
