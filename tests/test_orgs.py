import httpx
import pytest

from nodestream_github import GithubOrganizationsExtractor
from tests.data.orgs import (
    EXAMPLE_ORG,
    EXAMPLE_ORG_SUMMARY,
    GITHUB_ORG,
    GITHUB_ORG_SUMMARY,
)
from tests.data.repos import HELLO_WORLD_REPO
from tests.data.users import OCTOCAT_USER, TURBO_USER
from tests.mocks.githubrest import (
    DEFAULT_BASE_URL,
    DEFAULT_HOSTNAME,
    DEFAULT_PER_PAGE,
    GithubHttpxMock,
)

BASE_EXPECTED_GITHUB_ORG = {
    "advanced_security_enabled_for_new_repositories": False,
    "avatar_url": "https://github.com/images/error/octocat_happy.gif",
    "billing_email": "mona@github.com",
    "blog": "https://github.com/blog",
    "collaborators": 8,
    "company": "github",
    "created_at": "2008-01-14T04:33:35Z",
    "default_repository_permission": "read",
    "dependabot_alerts_enabled_for_new_repositories": False,
    "dependabot_security_updates_enabled_for_new_repositories": False,
    "dependency_graph_enabled_for_new_repositories": False,
    "description": "A great organization",
    "disk_usage": 10000,
    "email": "octocat@github.com",
    "events_url": "https://HOSTNAME/orgs/github/events",
    "followers": 20,
    "following": 0,
    "has_organization_projects": True,
    "has_repository_projects": True,
    "hooks_url": "https://HOSTNAME/orgs/github/hooks",
    "html_url": "https://github.com/github",
    "id": 1,
    "is_verified": True,
    "issues_url": "https://HOSTNAME/orgs/github/issues",
    "location": "San Francisco",
    "login": "github",
    "members_allowed_repository_creation_type": "all",
    "members_can_create_internal_repositories": False,
    "members_can_create_pages": True,
    "members_can_create_private_pages": True,
    "members_can_create_private_repositories": False,
    "members_can_create_public_pages": True,
    "members_can_create_public_repositories": False,
    "members_can_create_repositories": True,
    "members_can_fork_private_repositories": False,
    "members_url": "https://HOSTNAME/orgs/github/members{/member}",
    "name": "github",
    "node_id": "MDEyOk9yZ2FuaXphdGlvbjE=",
    "owned_private_repos": 100,
    "plan": {
        "filled_seats": 4,
        "name": "Medium",
        "private_repos": 20,
        "seats": 5,
        "space": 400,
    },
    "private_gists": 81,
    "public_gists": 1,
    "public_members_url": "https://HOSTNAME/orgs/github/public_members{/member}",
    "public_repos": 2,
    "repos_url": "https://HOSTNAME/orgs/github/repos",
    "repositories": [],
    "secret_scanning_enabled_for_new_repositories": False,
    "secret_scanning_push_protection_custom_link": (
        "https://github.com/octo-org/octo-repo/blob/main/im-blocked.md"
    ),
    "secret_scanning_push_protection_custom_link_enabled": False,
    "secret_scanning_push_protection_enabled_for_new_repositories": False,
    "total_private_repos": 100,
    "twitter_username": "github",
    "two_factor_requirement_enabled": True,
    "type": "Organization",
    "updated_at": "2014-03-03T18:58:10Z",
    "url": "https://HOSTNAME/orgs/github",
    "web_commit_signoff_required": False,
}


@pytest.fixture
def org_client() -> GithubOrganizationsExtractor:
    return GithubOrganizationsExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )


@pytest.mark.asyncio
async def test_orgs_continue_through_org_detail_status_fail(
    org_client: GithubOrganizationsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY, EXAMPLE_ORG_SUMMARY])
    gh_rest_mock.get_org("github", status_code=httpx.codes.NOT_FOUND)
    gh_rest_mock.get_org("example", json=EXAMPLE_ORG)

    gh_rest_mock.get_members_for_org("example", json=[], role="admin")
    gh_rest_mock.get_members_for_org("example", json=[], role="member")
    gh_rest_mock.get_repos_for_org("example", json=[])

    assert len([record async for record in org_client.extract_records()]) == 1


@pytest.mark.asyncio
async def test_orgs_continue_through_org_member_status_fail(
    org_client: GithubOrganizationsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_org("github", json=GITHUB_ORG)

    gh_rest_mock.get_members_for_org(
        "github",
        json=[],
        role="admin",
        status_code=httpx.codes.NOT_FOUND,
    )
    gh_rest_mock.get_members_for_org(
        "github",
        role="member",
        json=[TURBO_USER],
    )
    gh_rest_mock.get_repos_for_org("github", json=[HELLO_WORLD_REPO])

    assert [record async for record in org_client.extract_records()] == [
        BASE_EXPECTED_GITHUB_ORG
        | {
            "members": [{
                "id": 2,
                "login": "turbo",
                "node_id": "MDQ6VXNlcjI=",
                "role": "member",
            }],
            "repositories": [{
                "full_name": "octocat/Hello-World",
                "html_url": "https://github.com/octocat/Hello-World",
                "id": 1296269,
                "name": "Hello-World",
                "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                "permission": "read",
                "url": "https://HOSTNAME/repos/octocat/Hello-World",
            }],
        }
    ]


@pytest.mark.asyncio
async def test_orgs_continue_through_org_member_status_fail_second(
    org_client: GithubOrganizationsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_org("github", json=GITHUB_ORG)

    gh_rest_mock.get_members_for_org("github", json=[OCTOCAT_USER], role="admin")
    gh_rest_mock.get_members_for_org(
        "github",
        json=[],
        role="member",
        status_code=httpx.codes.NOT_FOUND,
    )
    gh_rest_mock.get_repos_for_org("github", json=[])

    assert [record async for record in org_client.extract_records()] == [
        BASE_EXPECTED_GITHUB_ORG
        | {
            "members": [{
                "id": 1,
                "login": "octocat",
                "node_id": "MDQ6VXNlcjE=",
                "role": "admin",
            }],
        }
    ]


@pytest.mark.asyncio
async def test_orgs_continue_through_org_repo_status_fail(
    org_client: GithubOrganizationsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_org("github", json=GITHUB_ORG)

    gh_rest_mock.get_members_for_org("github", json=[OCTOCAT_USER], role="admin")
    gh_rest_mock.get_members_for_org("github", json=[], role="member")
    gh_rest_mock.get_repos_for_org(
        "github",
        json=[],
        status_code=httpx.codes.NOT_FOUND,
    )

    assert [record async for record in org_client.extract_records()] == [
        BASE_EXPECTED_GITHUB_ORG
        | {
            "members": [{
                "id": 1,
                "login": "octocat",
                "node_id": "MDQ6VXNlcjE=",
                "role": "admin",
            }],
        }
    ]


@pytest.mark.asyncio
async def test_orgs_continue_through_org_detail_connection_fail(
    org_client: GithubOrganizationsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY, EXAMPLE_ORG_SUMMARY])
    gh_rest_mock.add_exception(
        exception=httpx.ReadTimeout("Mock Timeout Exception"),
        url=f"{DEFAULT_BASE_URL}/orgs/github",
        is_reusable=True,
    )
    gh_rest_mock.get_org("example", json=EXAMPLE_ORG)
    gh_rest_mock.get_members_for_org("example", json=[], role="admin")
    gh_rest_mock.get_members_for_org("example", json=[], role="member")
    gh_rest_mock.get_repos_for_org("example", json=[])

    assert len([record async for record in org_client.extract_records()]) == 1


@pytest.mark.asyncio
async def test_get_orgs(
    org_client: GithubOrganizationsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_org("github", json=GITHUB_ORG)
    gh_rest_mock.get_members_for_org("github", json=[OCTOCAT_USER], role="admin")
    gh_rest_mock.get_members_for_org("github", json=[TURBO_USER], role="member")
    gh_rest_mock.get_repos_for_org("github", json=[HELLO_WORLD_REPO])

    all_records = [record async for record in org_client.extract_records()]
    assert all_records == [
        BASE_EXPECTED_GITHUB_ORG
        | {
            "members": [
                {
                    "id": 1,
                    "login": "octocat",
                    "node_id": "MDQ6VXNlcjE=",
                    "role": "admin",
                },
                {
                    "id": 2,
                    "login": "turbo",
                    "node_id": "MDQ6VXNlcjI=",
                    "role": "member",
                },
            ],
            "repositories": [{
                "full_name": "octocat/Hello-World",
                "html_url": "https://github.com/octocat/Hello-World",
                "id": 1296269,
                "name": "Hello-World",
                "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                "permission": "read",
                "url": "https://HOSTNAME/repos/octocat/Hello-World",
            }],
        }
    ]


@pytest.mark.asyncio
async def test_skip_members(
    gh_rest_mock: GithubHttpxMock,
):
    org_client = GithubOrganizationsExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        include_members=False,
    )

    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_org("github", json=GITHUB_ORG)
    gh_rest_mock.get_repos_for_org("github", json=[HELLO_WORLD_REPO])

    all_records = [record async for record in org_client.extract_records()]
    assert all_records == [
        BASE_EXPECTED_GITHUB_ORG
        | {
            "members": [],
            "repositories": [{
                "full_name": "octocat/Hello-World",
                "html_url": "https://github.com/octocat/Hello-World",
                "id": 1296269,
                "name": "Hello-World",
                "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                "permission": "read",
                "url": "https://HOSTNAME/repos/octocat/Hello-World",
            }],
        }
    ]


@pytest.mark.asyncio
async def test_skip_repositories(gh_rest_mock: GithubHttpxMock):
    org_client = GithubOrganizationsExtractor(
        include_repositories="fart",
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )

    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_org("github", json=GITHUB_ORG)
    gh_rest_mock.get_members_for_org("github", json=[OCTOCAT_USER], role="admin")
    gh_rest_mock.get_members_for_org("github", json=[TURBO_USER], role="member")

    all_records = [record async for record in org_client.extract_records()]
    assert all_records == [
        BASE_EXPECTED_GITHUB_ORG
        | {
            "members": [
                {
                    "id": 1,
                    "login": "octocat",
                    "node_id": "MDQ6VXNlcjE=",
                    "role": "admin",
                },
                {
                    "id": 2,
                    "login": "turbo",
                    "node_id": "MDQ6VXNlcjI=",
                    "role": "member",
                },
            ],
            "repositories": [],
        }
    ]
