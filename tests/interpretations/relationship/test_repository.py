import pytest
from nodestream.model import DesiredIngestion, RelationshipCreationRule
from nodestream.pipeline.value_providers import ProviderContext

from nodestream_github.interpretations.relationship.repository import (
    RepositoryRelationshipInterpretation,
    simplify_repo,
)

_TEST_EXPECTATION = {
    "full_name": "test/fullName",
    "id": "test-id",
    "name": "test-name",
    "node_id": "test-node-id",
    "url": "test-url",
}


@pytest.fixture
def context() -> ProviderContext:
    return ProviderContext(_TEST_EXPECTATION, DesiredIngestion())


def test_simplify_repo():
    additional_keys = _TEST_EXPECTATION | {
        "do-not-include": "test-data",
        "a": "b",
        "c": [1, 2, 3],
        "d": True,
    }
    assert simplify_repo(additional_keys) == _TEST_EXPECTATION


def test_repo_relationship(context: ProviderContext):
    sample = RepositoryRelationshipInterpretation("TEST_RELATIONSHIP_TYPE")
    assert sample.node_type.single_value(context) == "GithubRepo"
    assert sample.relationship_type.single_value(context) == "TEST_RELATIONSHIP_TYPE"


def test_repo_relationship_forwards_optional_kwargs():
    sample = RepositoryRelationshipInterpretation(
        "TEST_RELATIONSHIP_TYPE",
        key_normalization={"do_lowercase_strings": False},
        properties_normalization={"do_lowercase_strings": True},
        node_additional_types=["Extra"],
    )
    assert sample.key_normalization == {"do_lowercase_strings": False}
    assert sample.properties_normalization == {"do_lowercase_strings": True}
    assert sample.node_additional_types == ("Extra",)


def test_repo_relationship_creation_rule_passthrough():
    sample = RepositoryRelationshipInterpretation(
        "TEST_RELATIONSHIP_TYPE", relationship_creation_rule="CREATE"
    )
    assert sample.relationship_creation_rule == RelationshipCreationRule.CREATE


def test_repo_relationship_creation_rule_defaults_to_eager():
    sample = RepositoryRelationshipInterpretation("TEST_RELATIONSHIP_TYPE")
    assert sample.relationship_creation_rule == RelationshipCreationRule.EAGER


def test_repo_relationship_creation_rule_invalid_raises():
    with pytest.raises(ValueError, match="BOGUS"):
        RepositoryRelationshipInterpretation(
            "TEST_RELATIONSHIP_TYPE", relationship_creation_rule="BOGUS"
        )
