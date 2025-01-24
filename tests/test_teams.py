import pytest

from nodestream_github import GithubTeamsExtractor
from tests.data.orgs import GITHUB_ORG_SUMMARY
from tests.data.repos import HELLO_WORLD_REPO
from tests.data.teams import JUSTICE_LEAGUE_TEAM, JUSTICE_LEAGUE_TEAM_SUMMARY
from tests.data.users import OCTOCAT_USER, TURBO_USER
from tests.mocks.githubrest import DEFAULT_HOSTNAME, DEFAULT_PER_PAGE, GithubHttpxMock


@pytest.fixture
def team_client() -> GithubTeamsExtractor:
    return GithubTeamsExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
    )


@pytest.mark.asyncio
async def test_extract_records(
    team_client: GithubTeamsExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.list_teams_for_org("github", json=[JUSTICE_LEAGUE_TEAM_SUMMARY])
    gh_rest_mock.get_team(
        org_login="github",
        team_slug="justice-league",
        json=JUSTICE_LEAGUE_TEAM,
    )
    gh_rest_mock.get_members_for_team(
        team_id=1,
        role="member",
        json=[OCTOCAT_USER],
    )
    gh_rest_mock.get_members_for_team(
        team_id=1,
        role="maintainer",
        json=[TURBO_USER],
    )
    gh_rest_mock.get_repos_for_team(
        org_login="github",
        slug="justice-league",
        json=[HELLO_WORLD_REPO],
    )

    assert [record async for record in team_client.extract_records()] == [{
        "created_at": "2017-07-14T16:53:42Z",
        "description": "A great team.",
        "html_url": "https://github.com/orgs/github/teams/justice-league",
        "id": 1,
        "ldap_dn": "uid=asdf,ou=users,dc=github,dc=com",
        "members": [
            {
                "id": 1,
                "login": "octocat",
                "node_id": "MDQ6VXNlcjE=",
                "role": "member",
            },
            {
                "id": 2,
                "login": "turbo",
                "node_id": "MDQ6VXNlcjI=",
                "role": "maintainer",
            },
        ],
        "members_count": 3,
        "members_url": "https://HOSTNAME/teams/1/members{/member}",
        "name": "Justice League",
        "node_id": "MDQ6VGVhbTE=",
        "notification_setting": "notifications_enabled",
        "organization": {
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
            "public_members_url": (
                "https://HOSTNAME/orgs/github/public_members{/member}"
            ),
            "public_repos": 2,
            "repos_url": "https://HOSTNAME/orgs/github/repos",
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
        },
        "parent": None,
        "permission": "admin",
        "privacy": "closed",
        "repos": [{
            "full_name": "octocat/Hello-World",
            "id": 1296269,
            "name": "Hello-World",
            "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
            "permission": "admin",
            "url": "https://HOSTNAME/repos/octocat/Hello-World",
        }],
        "repos_count": 10,
        "repositories_url": "https://HOSTNAME/teams/1/repos",
        "slug": "justice-league",
        "updated_at": "2017-08-17T12:37:15Z",
        "url": "https://HOSTNAME/teams/1",
    }]
