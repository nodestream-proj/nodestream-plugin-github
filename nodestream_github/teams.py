import logging
from typing import Any, AsyncGenerator

from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.util.githubclient import GithubRestApiClient
from nodestream_github.util.simplify import simplify_repo, simplify_user

logger = logging.getLogger(__name__)


class GithubTeamsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncGenerator[Any, Any]:
        async for page in self.client.get("organizations"):
            login = page["login"]
            try:
                async for team in self._get_teams(login):
                    yield team
            except HTTPStatusError as e:
                logger.debug("Problem getting team info for org '%s': %s", login, e)
            except HTTPError as e:
                logger.warning(
                    "Major problem getting team info for org '%s': %s", login, e
                )

    async def _fetch_members(self, team_id) -> AsyncGenerator[Any, Any]:
        logger.debug("Getting members for team %s", team_id)
        async for member in self.client.get(
            f"teams/{team_id}/members", {"role": "member"}
        ):
            member["role"] = "member"
            yield member

        async for maintainer in self.client.get(
            f"teams/{team_id}/members", {"role": "maintainer"}
        ):
            maintainer["role"] = "maintainer"
            yield maintainer

    async def _get_teams(self, login):
        logger.debug("Getting teams for %s", login)
        async for team_summary in self.client.get(
            f"orgs/{login}/teams",
        ):
            team = await self.client.get_item(f"teams/{team_summary['id']}")
            try:
                team["members"] = []
                async for response in self._fetch_members(team["id"]):
                    team["members"].append(simplify_user(response))
            except HTTPStatusError as e:
                logger.warning(
                    "Problem getting members for team '%s': %s", team["name"], e
                )
            try:
                team["repos"] = [
                    simplify_repo(response)
                    async for response in self.client.get(f"teams/{team['id']}/repos")
                ]
            except HTTPStatusError as e:
                logger.warning(
                    "Problem getting repos for team '%s': %s", team["name"], e
                )
            yield team
