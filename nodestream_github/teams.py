"""
Nodestream Extractor that creates GitHub team nodes from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator, Mapping
from typing import Any

from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.user import simplify_user

from .client import GithubRestApiClient
from .client.rest import OrgClient, TeamClient
from .interpretations.relationship.repository import simplify_repo
from .logging import get_plugin_logger
from .types.gh_model import NullableSimpleUser, Team, TeamFull, TeamMemberRole

logger = get_plugin_logger(__name__)


class GithubTeamsExtractor(Extractor):
    def __init__(self, **github_client_kwargs: Any):
        self.core_client = GithubRestApiClient(**github_client_kwargs)
        self.team_client = TeamClient(self.core_client)
        self.org_client = OrgClient(self.core_client)

    async def extract_records(self) -> AsyncGenerator[Mapping]:
        async for org in self.org_client.fetch_all_organizations():
            login = org["login"]
            async for team in self.team_client.fetch_teams_for_org(org_login=login):
                team_record = await self._fetch_team(login, team)
                if isinstance(team_record, Mapping) and team_record:
                    org = team_record.get("organization")
                    logger.debug(
                        "yielded GithubTeam{org=%s,slug=%s}",
                        org.get("login") if isinstance(org, Mapping) else None,
                        team_record["slug"],
                    )
                    yield team_record

    async def _fetch_members_by_role(
        self, team: TeamFull, role: TeamMemberRole
    ) -> AsyncGenerator[NullableSimpleUser]:
        logger.debug(
            "Getting members for team %s/%s",
            team["organization"]["login"],
            team["slug"],
        )

        async for member in self.team_client.fetch_members_for_team(
            team_id=team["id"], role=role
        ):
            yield member

    async def _fetch_team(
        self, login: str, team_summary: Team
    ) -> dict[str, Any] | None:
        team = await self.team_client.fetch_team(
            org_login=login,
            slug=team_summary["slug"],
        )
        if not team:
            return None
        output = {**team}
        members: list[dict[str, Any]] = []
        members += [
            simplify_user(m) | {"role": "member"}
            async for m in self._fetch_members_by_role(team, TeamMemberRole.member)
        ]

        members += [
            simplify_user(m) | {"role": "maintainer"}
            async for m in self._fetch_members_by_role(team, TeamMemberRole.maintainer)
        ]
        output["members"] = members

        output["repos"] = [
            simplify_repo(repo)
            async for repo in self.team_client.fetch_repos_for_team(
                org_login=login,
                slug=team["slug"],
            )
        ]
        return output
