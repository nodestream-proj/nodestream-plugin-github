import logging

from httpx import HTTPStatusError
from nodestream.pipeline import Extractor

from nodestream_github.interpretations.relationship.user import simplify_user
from nodestream_github.util.githubclient import GithubRestApiClient

logger = logging.getLogger(__name__)


class GithubReposExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self):
        async for page in self.client.get("repositories"):
            yield await self._extract_repo(page)

    #        async for page in self.client.get_repos():
    #            yield await self._extract_repo(page)

    async def _extract_repo(self, repo):
        logger.debug("Extracting repo %s", repo["full_name"])
        repo_full_name = repo["full_name"]
        owner = repo.get("owner", {})
        if owner.get("type") == "User":
            repo["user_owner"] = owner
        elif owner:
            repo["org_owner"] = owner
        try:
            repo["languages"] = [
                {"name": lang_resp}
                async for lang_resp in self.client.get(
                    f"repos/{repo_full_name}/languages"
                )
            ]
        except HTTPStatusError as e:
            logger.debug("Problem getting languages for '%s': %s", repo_full_name, e)
        try:
            repo["webhooks"] = [
                wh_resp
                async for wh_resp in self.client.get(f"repos/{repo_full_name}/webhooks")
            ]
        except HTTPStatusError as e:
            logger.debug("Problem getting webhooks for '%s': %s", repo_full_name, e)
        try:
            repo["collaborators"] = [
                simplify_user(collab_resp)
                async for collab_resp in self.client.get(
                    f"repos/{repo_full_name}/collaborators"
                )
            ]
        except HTTPStatusError as e:
            logger.debug(
                "Problem getting collaborators for '%s': %s", repo_full_name, e
            )
        return repo
