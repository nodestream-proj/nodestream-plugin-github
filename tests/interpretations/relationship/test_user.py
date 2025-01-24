import pytest
from nodestream.model import DesiredIngestion
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
