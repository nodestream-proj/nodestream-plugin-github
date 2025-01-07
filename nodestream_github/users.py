import logging
from typing import AsyncIterator

from httpx import HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.util.githubclient import GithubRestApiClient
from nodestream_github.util.types import SimplifiedRepo, UserRecord

logger = logging.getLogger(__name__)


class GithubUserExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[UserRecord]:
        async for user in self.client.get("users"):
            login = user["login"]
            user["repositories"] = [repo async for repo in self._fetch_repos(login)]
            yield user

    async def _fetch_repos(self, login) -> AsyncIterator[SimplifiedRepo]:
        try:
            async for response in self.client.get(
                f"users/{login}/repos", {"type": "all"}
            ):
                yield simplify_repo(response)
        except HTTPStatusError as e:
            logger.warning("Problem getting repos for user %s", login, exc_info=e)
