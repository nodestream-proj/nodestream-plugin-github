import logging
from typing import AsyncGenerator

from httpx import HTTPError, HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.interpretations.relationship.user import simplify_user
from nodestream_github.util.githubclient import GithubRestApiClient

logger = logging.getLogger(__name__)


class GithubTeamsExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncGenerator[any, any]:
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

    async def _fetch_members(self, login: str, slug: str):
        logger.debug("Getting members for team %s/%s", login, slug)
        async for member in self.client.get(
            f"orgs/{login}/teams/{slug}/members", {"role": "member"}
        ):
            if member:
                member["role"] = "member"
                yield member

        async for maintainer in self.client.get(
            f"orgs/{login}/teams/{slug}/members", {"role": "maintainer"}
        ):
            if maintainer:
                maintainer["role"] = "maintainer"
                yield maintainer

    async def _get_teams(self, login):
        logger.debug("Getting teams for %s", login)
        async for team_summary in self.client.get(
            f"orgs/{login}/teams",
        ):
            team = await self.client.get_item(
                f"orgs/{login}/teams/{team_summary['slug']}"
            )
            try:
                team["members"] = [
                    simplify_user(response)
                    async for response in self._fetch_members(login, team["slug"])
                ]
            except HTTPStatusError as e:
                logger.warning(
                    "Problem getting members for team '%s': %s", team["name"], e
                )
            try:
                team["repos"] = [
                    simplify_repo(response)
                    async for response in self.client.get(
                        f"orgs/{login}/teams/{team['slug']}/repos"
                    )
                ]
            except HTTPStatusError as e:
                logger.warning(
                    "Problem getting repos for team '%s/%s': %s", login, team["slug"], e
                )
            yield team
