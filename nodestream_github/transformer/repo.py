import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Mapping
from typing import Any

from nodestream.pipeline import Transformer

from nodestream_github.client import GithubRestApiClient
from nodestream_github.client.rest import RepoClient
from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.logging import get_plugin_logger
from nodestream_github.types.enums import CollaboratorAffiliation

logger = get_plugin_logger(__name__)


class RepoFullNameTransformer(Transformer, ABC):
    def __init__(
        self,
        *,
        full_name_key: str = "full_name",
        **kwargs: Any,
    ):
        self.core_client = GithubRestApiClient(**kwargs)
        self.full_name_key = full_name_key
        self.repo_client = RepoClient(self.core_client)

    async def transform_record(self, record: Any) -> Any:  # noqa: ANN401
        logging.debug("attempting to transform %s", record)
        if isinstance(record, Mapping):
            full_name = record.get(self.full_name_key)
            simplified_repo = simplify_repo(record)

            if full_name is not None:
                async for user in self._transform(str(full_name), simplified_repo):
                    yield user
            else:
                logging.info("No full_name key found in record %s", record)

    @abstractmethod
    def _transform(
        self,
        full_name: str,
        simplified_repo: dict[str, Any],
    ) -> AsyncGenerator[dict[str, Any]]:
        raise NotImplementedError


class RepoToUserCollaboratorsTransformer(RepoFullNameTransformer):
    def __init__(self, *, full_name_key: str = "full_name", **kwargs: Any):
        super().__init__(full_name_key=full_name_key, **kwargs)

    async def _transform(
        self, full_name: str, simplified_repo: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any]]:
        repo_owner, repo_name = full_name.split("/")

        logging.debug("Transforming repo %s/%s", repo_owner, repo_name)

        async for collaborator in self.repo_client.fetch_collaborators_for_repo(
            owner_login=repo_owner,
            repo_name=repo_name,
            affiliation=CollaboratorAffiliation.DIRECT,
        ):
            yield {
                **collaborator,
                "repository": simplified_repo,
                "affiliation": CollaboratorAffiliation.DIRECT,
            }

        async for collaborator in self.repo_client.fetch_collaborators_for_repo(
            owner_login=repo_owner,
            repo_name=repo_name,
            affiliation=CollaboratorAffiliation.OUTSIDE,
        ):
            yield {
                **collaborator,
                "repository": simplified_repo,
                "affiliation": CollaboratorAffiliation.OUTSIDE,
            }


class RepoToTeamCollaboratorsTransformer(RepoFullNameTransformer):
    async def _transform(
        self, full_name: str, simplified_repo: dict[str, Any]
    ) -> AsyncGenerator[dict[str, Any]]:
        repo_owner, repo_name = full_name.split("/")

        logging.debug("Transforming repo %s/%s", repo_owner, repo_name)

        async for collaborator in self.repo_client.fetch_teams_for_repo(
            owner_login=repo_owner,
            repo_name=repo_name,
        ):
            logging.debug("Found team %s", collaborator)
            yield collaborator | {"repository": simplified_repo}
