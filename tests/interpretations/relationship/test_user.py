import pytest
from nodestream.model import DesiredIngestion, RelationshipCreationRule
from nodestream.pipeline.value_providers import ProviderContext

from nodestream_github.interpretations.relationship.user import (
    UserRelationshipInterpretation,
    simplify_user,
)
from nodestream_github.types.gh_model import NullableSimpleUser

_TEST_DATA = NullableSimpleUser(
    login="test-login",
    id=888999,
    node_id="test-node-id",
    avatar_url="https://test_avatar_url.example.com",
    gravatar_id="1234",
    url="https://test_url.example.com",
    html_url="https://test_html_url.example.com",
    followers_url="https://test_followers_url.example.com",
    following_url="https://test_following_url.example.com",
    gists_url="https://test_gists_url.example.com",
    starred_url="https://test_starred_url.example.com",
    subscriptions_url="https://test_subscriptions_url.example.com",
    organizations_url="https://test_organizations_url.example.com",
    repos_url="https://test_organizations_url.example.com",
    events_url="https://test_events_url.example.com",
    received_events_url="https://test_received_events_url.example.com",
    type="user",
    site_admin=False,
)


@pytest.fixture
def context() -> ProviderContext:
    return ProviderContext({**_TEST_DATA}, DesiredIngestion())


def test_simplify_user():
    additional_keys = _TEST_DATA
    assert simplify_user(additional_keys) == {
        "id": 888999,
        "login": "test-login",
        "node_id": "test-node-id",
    }


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
