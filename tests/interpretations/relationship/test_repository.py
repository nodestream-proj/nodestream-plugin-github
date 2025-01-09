import pytest
from nodestream.model import DesiredIngestion
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


def test_simplify_repo_keep_perms():
    test_input = _TEST_EXPECTATION | {"permissions": {"admin": True}}
    assert simplify_repo(test_input) == test_input


def test_repo_relationship(context: ProviderContext):
    sample = RepositoryRelationshipInterpretation("TEST_RELATIONSHIP_TYPE")
    assert sample.node_type.single_value(context) == "GithubRepo"
    assert sample.relationship_type.single_value(context) == "TEST_RELATIONSHIP_TYPE"
