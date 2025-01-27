from collections.abc import Iterable
from typing import Any

from nodestream.interpreting.interpretations import RelationshipInterpretation
from nodestream.pipeline.value_providers import (
    JmespathValueProvider,
    StaticValueOrValueProvider,
    ValueProvider,
)

from nodestream_github.types import GithubRepo, SimplifiedRepo

_REPO_KEYS_TO_PRESERVE = ["id", "node_id", "name", "full_name", "url", "permission"]


def simplify_repo(repo: GithubRepo, *, permission: str | None = None) -> SimplifiedRepo:
    """Simplify repo data.

    Allows us to only keep a consistent minimum for relationship data."""
    output = {k: repo[k] for k in _REPO_KEYS_TO_PRESERVE if k in repo}

    if permission:
        output["permission"] = permission
    return output


class RepositoryRelationshipInterpretation(
    RelationshipInterpretation, alias="github-repo-relationship"
):
    def __init__(
        self,
        relationship_type: StaticValueOrValueProvider,
        relationship_key: None | dict[str, StaticValueOrValueProvider] = None,
        relationship_properties: None | dict[str, StaticValueOrValueProvider] = None,
        outbound: bool = True,  # noqa: FBT001, FBT002
        find_many: bool = False,  # noqa: FBT001, FBT002
        iterate_on: ValueProvider | None = None,
        cardinality: str = "SINGLE",
        node_creation_rule: str | None = None,
        key_normalization: dict[str, Any] | None = None,
        properties_normalization: dict[str, Any] | None = None,
        node_additional_types: Iterable[str] | None = None,
    ):
        super().__init__(
            "GithubRepo",
            relationship_type,
            {"node_id": JmespathValueProvider.from_string_expression("node_id")},
            {
                "id": JmespathValueProvider.from_string_expression("id"),
                "name": JmespathValueProvider.from_string_expression("name"),
                "full_name": JmespathValueProvider.from_string_expression("full_name"),
                "url": JmespathValueProvider.from_string_expression("url"),
            },
            relationship_key,
            relationship_properties,
            outbound,
            find_many,
            iterate_on,
            cardinality,
            node_creation_rule,
            key_normalization,
            properties_normalization,
            node_additional_types,
        )
