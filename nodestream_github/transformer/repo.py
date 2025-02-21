import logging
from collections.abc import AsyncGenerator

from nodestream.pipeline import Transformer

from nodestream_github import types
from nodestream_github.client import GithubRestApiClient
from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.logging import get_plugin_logger
from nodestream_github.types.enums import CollaboratorAffiliation

logger = get_plugin_logger(__name__)


class RepoToCollaboratorsTransformer(Transformer):
    def __init__(
        self,
        *,
        full_name_key: str = "full_name",
        **kwargs: any,
    ):

        self.client = GithubRestApiClient(**kwargs)
        self.full_name_key = full_name_key

    async def transform_record(
        self,
        record: types.GithubRepo,
    ) -> AsyncGenerator[types.GithubUser]:
        (repo_owner, repo_name) = record[self.full_name_key].split("/")
        logging.debug("Transforming record %s/%s", repo_owner, repo_name)

        simplified_repo = simplify_repo(record)

        async for collaborator in self.client.fetch_collaborators_for_repo(
            owner_login=repo_owner,
            repo_name=repo_name,
            affiliation=CollaboratorAffiliation.DIRECT,
        ):
            yield collaborator | {
                "repository": simplified_repo,
                "affiliation": CollaboratorAffiliation.DIRECT,
            }

        async for collaborator in self.client.fetch_collaborators_for_repo(
            owner_login=repo_owner,
            repo_name=repo_name,
            affiliation=CollaboratorAffiliation.OUTSIDE,
        ):
            yield collaborator | {
                "repository": simplified_repo,
                "affiliation": CollaboratorAffiliation.OUTSIDE,
            }
