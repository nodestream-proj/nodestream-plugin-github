from typing import Any, Iterable

from nodestream.interpreting.interpretations import RelationshipInterpretation
from nodestream.pipeline.value_providers import (
    JmespathValueProvider,
    StaticValueOrValueProvider,
    ValueProvider,
)

from nodestream_github.util.types import GithubUser, SimplifiedUser


def simplify_user(user: GithubUser) -> SimplifiedUser:
    """Simplify user data.

    Allows us to only keep a consistent minimum for relationship data."""
    data = {
        "id": user["id"],
        "login": user["login"],
        "node_id": user["node_id"],
    }
    if "role" in user:
        data["role"] = user["role"]
    if "permissions" in user:
        data["permissions"] = user["permissions"]
    return data


class UserRelationshipInterpretation(
    RelationshipInterpretation, alias="github-user-relationship"
):
    def __init__(
        self,
        relationship_type: StaticValueOrValueProvider,
        relationship_key: None | dict[str, StaticValueOrValueProvider] = None,
        relationship_properties: None | dict[str, StaticValueOrValueProvider] = None,
        outbound: bool = True,
        find_many: bool = False,
        iterate_on: ValueProvider | None = None,
        cardinality: str = "SINGLE",
        node_creation_rule: str | None = None,
        key_normalization: dict[str, Any] = None,
        properties_normalization: dict[str, Any] | None = None,
        node_additional_types: Iterable[str] | None = None,
    ):
        super().__init__(
            "GithubUser",
            relationship_type,
            {"node_id": JmespathValueProvider.from_string_expression("node_id")},
            {
                "id": JmespathValueProvider.from_string_expression("id"),
                "login": JmespathValueProvider.from_string_expression("login"),
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
