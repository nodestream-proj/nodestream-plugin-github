from collections.abc import AsyncGenerator

import httpx2

from nodestream_github.client.rest.githubclient import (
    GithubRestApiClient,
    log_fetch_problem,
)
from nodestream_github.logging import get_plugin_logger
from nodestream_github.types.gh_model import (
    MinimalRepository,
    NullableSimpleUser,
    Team,
    TeamFull,
    TeamMemberRole,
)

logger = get_plugin_logger(__name__)


class TeamClient:
    def __init__(self, client: GithubRestApiClient):
        self.client: GithubRestApiClient = client

    async def fetch_teams_for_org(
        self,
        *,
        org_login: str,
    ) -> AsyncGenerator[Team]:
        """Fetch all teams in an organization visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-teams

        Fine-grained tokens must have the "Members" organization permissions (read)
        """
        try:
            logger.debug("Fetch teams for %s", org_login)
            async for team_summary in self.client.get_paginated(
                f"orgs/{org_login}/teams",
            ):
                yield Team(**team_summary)

        except httpx2.HTTPError as e:
            log_fetch_problem(f"teams for org {org_login}", e)

    async def fetch_team(self, *, org_login: str, slug: str) -> TeamFull | None:
        """Fetches a single team for an org by the team slug.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#get-a-team-by-name
        """
        try:
            return TeamFull(
                **await self.client.get_item(f"orgs/{org_login}/teams/{slug}")
            )
        except httpx2.HTTPError as e:
            log_fetch_problem(f"full team info for {org_login}/{slug}", e)
            return None

    async def fetch_members_for_team(
        self,
        *,
        team_id: int,
        role: TeamMemberRole | None = None,
    ) -> AsyncGenerator[NullableSimpleUser]:
        """Fetch all users that have a given role for a specified team.

        These endpoints are only available to authenticated members of the
        team's organization.

        Access tokens require the read:org scope.

        To list members in a team, the team must be visible to the authenticated user.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/members?apiVersion=2022-11-28#list-team-members-legacy
        """
        try:
            params = {}
            if role:
                params["role"] = role
            async for member in self.client.get_paginated(
                f"teams/{team_id}/members", params=params
            ):
                yield NullableSimpleUser(**member)
        except httpx2.HTTPError as e:
            log_fetch_problem(f"members for team {team_id}", e)

    async def fetch_repos_for_team(
        self,
        *,
        org_login: str,
        slug: str,
    ) -> AsyncGenerator[MinimalRepository]:
        """Fetch all repos for a specified team visible to the authenticated user.

        These endpoints are only available to authenticated members of the
        team's organization.

        https://docs.github.com/en/enterprise-server@3.12/rest/teams/teams?apiVersion=2022-11-28#list-team-repositories
        """
        try:
            async for repo in self.client.get_paginated(
                f"orgs/{org_login}/teams/{slug}/repos"
            ):
                yield MinimalRepository(**repo)
        except httpx2.HTTPError as e:
            log_fetch_problem(f"repos for team {org_login}/{slug}", e)
