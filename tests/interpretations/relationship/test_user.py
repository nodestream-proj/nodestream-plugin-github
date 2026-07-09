import pytest
from nodestream.model import DesiredIngestion, RelationshipCreationRule
from nodestream.pipeline.value_providers import ProviderContext

from nodestream_github.interpretations.relationship.user import (
    UserRelationshipInterpretation,
    simplify_user,
)

_TEST_EXPECTATION = {
    "login": "test-login",
    "id": "test-id",
    "node_id": "test-node-id",
}


@pytest.fixture
def context() -> ProviderContext:
    return ProviderContext(_TEST_EXPECTATION, DesiredIngestion())


def test_simplify_user():
    additional_keys = _TEST_EXPECTATION | {
        "do-not-include": "test-data",
        "a": "b",
        "c": [1, 2, 3],
        "d": True,
    }
    assert simplify_user(additional_keys) == _TEST_EXPECTATION


def test_simplify_user_identity():
    assert simplify_user(_TEST_EXPECTATION) == _TEST_EXPECTATION


def test_user_relationship(context: ProviderContext):
    sample = UserRelationshipInterpretation("TEST_RELATIONSHIP_TYPE")
    assert sample.node_type.single_value(context) == "GithubUser"
    assert sample.relationship_type.single_value(context) == "TEST_RELATIONSHIP_TYPE"


def test_user_relationship_forwards_optional_kwargs():
    sample = UserRelationshipInterpretation(
        "TEST_RELATIONSHIP_TYPE",
        key_normalization={"do_lowercase_strings": False},
        properties_normalization={"do_lowercase_strings": True},
        node_additional_types=["Extra"],
    )
    assert sample.key_normalization["do_lowercase_strings"] is False
    assert sample.properties_normalization == {"do_lowercase_strings": True}
    assert sample.node_additional_types == ("Extra",)


def test_user_relationship_creation_rule_passthrough():
    sample = UserRelationshipInterpretation(
        "TEST_RELATIONSHIP_TYPE", relationship_creation_rule="CREATE"
    )
    assert sample.relationship_creation_rule == RelationshipCreationRule.CREATE


def test_user_relationship_creation_rule_defaults_to_eager():
    sample = UserRelationshipInterpretation("TEST_RELATIONSHIP_TYPE")
    assert sample.relationship_creation_rule == RelationshipCreationRule.EAGER


def test_user_relationship_creation_rule_invalid_raises():
    with pytest.raises(ValueError, match="BOGUS"):
        UserRelationshipInterpretation(
            "TEST_RELATIONSHIP_TYPE", relationship_creation_rule="BOGUS"
        )
