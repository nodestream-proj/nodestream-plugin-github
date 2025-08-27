import pytest

from nodestream_github.interpretations.relationship.repository import simplify_repo
from nodestream_github.transformer.repo import RepoToTeamCollaboratorsTransformer
from tests.data.repos import HELLO_WORLD_REPO
from tests.data.teams import JUSTICE_LEAGUE_TEAM_SUMMARY
from tests.mocks.githubrest import DEFAULT_HOSTNAME, DEFAULT_PER_PAGE, GithubHttpxMock

REPO_TEAM_SUMMARY = {
    "id": 1,
    "node_id": "MDQ6VGVhbTE=",
    "url": "https://HOSTNAME/teams/1",
    "html_url": "https://github.com/orgs/github/teams/justice-league",
    "name": "Justice League",
    "slug": "justice-league",
    "description": "A great team.",
    "privacy": "closed",
    "notification_setting": "notifications_enabled",
    "permission": "admin",
    "members_url": "https://HOSTNAME/teams/1/members{/member}",
    "repositories_url": "https://HOSTNAME/teams/1/repos",
    "parent": None,
}


@pytest.mark.asyncio
async def test_transform_records(gh_rest_mock: GithubHttpxMock):
    transformer = RepoToTeamCollaboratorsTransformer(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )

    gh_rest_mock.get_teams_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        json=[REPO_TEAM_SUMMARY],
    )
    repo_summary = simplify_repo(HELLO_WORLD_REPO)

    response = [r async for r in transformer.transform_record(HELLO_WORLD_REPO)]

    assert response == [JUSTICE_LEAGUE_TEAM_SUMMARY | {"repository": repo_summary}]


@pytest.mark.asyncio
async def test_transform_records_alt_key(gh_rest_mock: GithubHttpxMock):
    transformer = RepoToTeamCollaboratorsTransformer(
        full_name_key="nameWithOwner",
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )

    gh_rest_mock.get_teams_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        json=[JUSTICE_LEAGUE_TEAM_SUMMARY],
    )

    modified_repo = HELLO_WORLD_REPO | {"nameWithOwner": "octocat/Hello-World"}
    del modified_repo["full_name"]
    repo_summary = simplify_repo(modified_repo)

    response = [r async for r in transformer.transform_record(modified_repo)]

    assert response == [JUSTICE_LEAGUE_TEAM_SUMMARY | {"repository": repo_summary}]


@pytest.mark.asyncio
async def test_no_full_name_key():
    transformer = RepoToTeamCollaboratorsTransformer(
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
