import logging

from httpx import HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.util.githubclient import GithubRestApiClient

logger = logging.getLogger(__name__)


class GithubUserExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        print(github_client_kwargs)
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self):
        async for user in self.client.get_users():
            login = user["login"]
            try:
                user["repos"] = []
                async for response in self.client.get(
                    f"users/{login}/collaborators", {"type": "owner"}
                ):
                    user["repos"].append(simplify_repo(response))

            except HTTPStatusError as e:
                logger.warning("Problem getting repos for user %s", login, exc_info=e)
            yield user
