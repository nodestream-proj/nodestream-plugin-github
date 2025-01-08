from typing import AsyncIterator

from httpx import HTTPStatusError
from nodestream.pipeline import Extractor

from .interpretations.relationship.user import simplify_user
from .types import GithubRepo, LanguageRecord, RepositoryRecord, SimplifiedUser, Webhook
from .util import GithubRestApiClient, init_logger

logger = init_logger(__name__)


class GithubReposExtractor(Extractor):
    def __init__(self, **github_client_kwargs):
        self.client = GithubRestApiClient(**github_client_kwargs)

    async def extract_records(self) -> AsyncIterator[RepositoryRecord]:
        async for page in self.client.get("repositories"):
            yield await self._extract_repo(page)

    #        async for page in self.client.get_repos():
    #            yield await self._extract_repo(page)

    async def _extract_repo(self, repo: GithubRepo) -> RepositoryRecord:
        logger.debug("Extracting repo %s", repo["full_name"])
        repo_full_name = repo["full_name"]
        owner = repo.get("owner", {})
        if owner.get("type") == "User":
            repo["user_owner"] = owner
        elif owner:
            repo["org_owner"] = owner
        repo["languages"] = [
            language async for language in self._fetch_languages(repo_full_name)
        ]
        repo["webhooks"] = [
            webhook async for webhook in self._fetch_webhooks(repo_full_name)
        ]
        repo["collaborators"] = [
            collaborator
            async for collaborator in self._fetch_collaborators(repo_full_name)
        ]
        return repo

    async def _fetch_languages(
        self, repo_full_name: str
    ) -> AsyncIterator[LanguageRecord]:
        try:

            async for lang_resp in self.client.get(f"repos/{repo_full_name}/languages"):
                yield {"name": lang_resp}
        except HTTPStatusError as e:
            logger.debug("Problem getting languages for '%s': %s", repo_full_name, e)

    async def _fetch_collaborators(
        self, repo_full_name: str
    ) -> AsyncIterator[SimplifiedUser]:
        try:
            async for collab_resp in self.client.get(
                f"repos/{repo_full_name}/collaborators"
            ):
                yield simplify_user(collab_resp)

        except HTTPStatusError as e:
            logger.debug(
                "Problem getting collaborators for '%s': %s", repo_full_name, e
            )

    async def _fetch_webhooks(self, repo_full_name: str) -> AsyncIterator[Webhook]:
        try:
            async for wh_resp in self.client.get(f"repos/{repo_full_name}/webhooks"):
                yield wh_resp
        except HTTPStatusError as e:
            logger.debug("Problem getting webhooks for '%s': %s", repo_full_name, e)
