import pytest

from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.transformer.repo import RepoToUserCollaboratorsTransformer
from nodestream_github.types.enums import CollaboratorAffiliation
from tests.data.repos import HELLO_WORLD_REPO
from tests.data.users import OCTOCAT_USER_SHORT, TURBO_USER_SHORT
from tests.mocks.githubrest import DEFAULT_HOSTNAME, DEFAULT_PER_PAGE, GithubHttpxMock


@pytest.mark.asyncio
async def test_transform_records(gh_rest_mock: GithubHttpxMock):
    transformer = RepoToUserCollaboratorsTransformer(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )

    gh_rest_mock.get_collaborators_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        affiliation=CollaboratorAffiliation.DIRECT,
        json=[OCTOCAT_USER_SHORT],
    )
    gh_rest_mock.get_collaborators_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        affiliation=CollaboratorAffiliation.OUTSIDE,
        json=[TURBO_USER_SHORT],
    )

    repo_summary = simplify_repo(HELLO_WORLD_REPO)

    response = [r async for r in transformer.transform_record(HELLO_WORLD_REPO)]

    assert response == [
        OCTOCAT_USER_SHORT | {"repository": repo_summary, "affiliation": "direct"},
        TURBO_USER_SHORT | {"repository": repo_summary, "affiliation": "outside"},
    ]


@pytest.mark.asyncio
async def test_transform_records_alt_key(gh_rest_mock: GithubHttpxMock):
    transformer = RepoToUserCollaboratorsTransformer(
        full_name_key="nameWithOwner",
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )

    gh_rest_mock.get_collaborators_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        affiliation=CollaboratorAffiliation.DIRECT,
        json=[OCTOCAT_USER_SHORT],
    )
    gh_rest_mock.get_collaborators_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        affiliation=CollaboratorAffiliation.OUTSIDE,
        json=[TURBO_USER_SHORT],
    )

    modified_repo = HELLO_WORLD_REPO | {"nameWithOwner": "octocat/Hello-World"}
    del modified_repo["full_name"]
    repo_summary = simplify_repo(modified_repo)

    response = [r async for r in transformer.transform_record(modified_repo)]

    assert response == [
        OCTOCAT_USER_SHORT | {"repository": repo_summary, "affiliation": "direct"},
        TURBO_USER_SHORT | {"repository": repo_summary, "affiliation": "outside"},
    ]


@pytest.mark.asyncio
async def test_no_full_name_key():
    transformer = RepoToUserCollaboratorsTransformer(
        full_name_key="full_name",
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )
    modified_repo = HELLO_WORLD_REPO.copy()
    del modified_repo["full_name"]

    response = [r async for r in transformer.transform_record(modified_repo)]
    assert response == []
