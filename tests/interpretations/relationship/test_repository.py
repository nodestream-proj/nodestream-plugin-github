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


def test_simplify_repo_set_perm():
    expected = _TEST_EXPECTATION | {"permission": "test"}
    assert simplify_repo(_TEST_EXPECTATION, permission="test") == expected


def test_repo_relationship(context: ProviderContext):
    sample = RepositoryRelationshipInterpretation("TEST_RELATIONSHIP_TYPE")
    assert sample.node_type.single_value(context) == "GithubRepo"
    assert sample.relationship_type.single_value(context) == "TEST_RELATIONSHIP_TYPE"
