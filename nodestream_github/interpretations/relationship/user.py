from typing import Any, Iterable

from nodestream.interpreting.interpretations import RelationshipInterpretation
from nodestream.pipeline.value_providers import (
    JmespathValueProvider,
    StaticValueOrValueProvider,
    ValueProvider,
)


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
