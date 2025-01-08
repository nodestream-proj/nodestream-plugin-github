import pytest

from nodestream_github import GithubReposExtractor
from tests.data.orgs import GITHUB_ORG_SUMMARY
from tests.data.repos import HELLO_WORLD_REPO, repo
from tests.data.users import OCTOCAT_USER, TURBO_USER
from tests.data.webhooks import HELLO_WORLD_WEBHOOK
from tests.mocks.githubrest import DEFAULT_ENDPOINT, DEFAULT_PER_PAGE, GithubHttpxMock


@pytest.fixture
def repo_client():
    return GithubReposExtractor(
        auth_token="test-token",
        github_endpoint=DEFAULT_ENDPOINT,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        collecting={"all_public": True},
    )


@pytest.mark.asyncio
async def test_pull_org_repos(gh_rest_mock):
    extractor = GithubReposExtractor(
        auth_token="test-token",
        github_endpoint=DEFAULT_ENDPOINT,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        collecting={"org_all": True},
    )

    gh_rest_mock.all_orgs(json=[GITHUB_ORG_SUMMARY])
    gh_rest_mock.get_repos_for_org("github", "public", json=[HELLO_WORLD_REPO])
    gh_rest_mock.get_repos_for_org("github", "private", json=[HELLO_WORLD_REPO])
    gh_rest_mock.get_languages_for_repo(
        "octocat", "Hello-World", json=[], is_reusable=True
    )
    gh_rest_mock.get_webhooks_for_repo(
        "octocat", "Hello-World", json=[], is_reusable=True
    )
    gh_rest_mock.get_collaborators_for_repo(
        "octocat", "Hello-World", json=[], is_reusable=True
    )

    assert len([record async for record in extractor.extract_records()]) == 2


@pytest.mark.asyncio
async def test_pull_user_repos(gh_rest_mock):
    extractor = GithubReposExtractor(
        auth_token="test-token",
        github_endpoint=DEFAULT_ENDPOINT,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        collecting={"user_all": True},
    )

    gh_rest_mock.all_users(json=[OCTOCAT_USER])
    gh_rest_mock.get_repos_for_user("octocat", "public", json=[HELLO_WORLD_REPO])
    gh_rest_mock.get_repos_for_user("octocat", "private", json=[HELLO_WORLD_REPO])
    gh_rest_mock.get_languages_for_repo(
        "octocat", "Hello-World", json=[], is_reusable=True
    )
    gh_rest_mock.get_webhooks_for_repo(
        "octocat", "Hello-World", json=[], is_reusable=True
    )
    gh_rest_mock.get_collaborators_for_repo(
        "octocat", "Hello-World", json=[], is_reusable=True
    )

    assert len([record async for record in extractor.extract_records()]) == 2


@pytest.mark.asyncio
async def test_extract_records(
    repo_client: GithubReposExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.all_repos(
        json=[HELLO_WORLD_REPO, repo(owner=GITHUB_ORG_SUMMARY, repo_name="Hello-Moon")],
    )
    gh_rest_mock.get_languages_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        json=["Java", "OCaml"],
    )
    gh_rest_mock.get_webhooks_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        json=[HELLO_WORLD_WEBHOOK],
    )
    gh_rest_mock.get_collaborators_for_repo(
        owner_login="octocat",
        repo_name="Hello-World",
        json=[TURBO_USER],
    )
    gh_rest_mock.get_languages_for_repo(
        owner_login="github",
        repo_name="Hello-Moon",
        json=["golang", "perl"],
    )
    gh_rest_mock.get_webhooks_for_repo(
        owner_login="github",
        repo_name="Hello-Moon",
        json=[HELLO_WORLD_WEBHOOK],
    )
    gh_rest_mock.get_collaborators_for_repo(
        owner_login="github",
        repo_name="Hello-Moon",
        json=[TURBO_USER],
    )
    assert [record async for record in repo_client.extract_records()] == [
        {
            "archive_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/{archive_format}{/ref}"
            ),
            "archived": False,
            "assignees_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/assignees{/user}"
            ),
            "blobs_url": "https://HOSTNAME/repos/octocat/Hello-World/git/blobs{/sha}",
            "branches_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/branches{/branch}"
            ),
            "clone_url": "https://github.com/octocat/Hello-World.git",
            "collaborators": [{"id": 2, "login": "turbo", "node_id": "MDQ6VXNlcjI="}],
            "collaborators_url": "https://HOSTNAME/repos/octocat/Hello-World/collaborators{/collaborator}",
            "comments_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/comments{/number}"
            ),
            "commits_url": "https://HOSTNAME/repos/octocat/Hello-World/commits{/sha}",
            "compare_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/compare/{base}...{head}"
            ),
            "contents_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/contents/{+path}"
            ),
            "contributors_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/contributors"
            ),
            "created_at": "2011-01-26T19:01:12Z",
            "default_branch": "master",
            "deployments_url": "https://HOSTNAME/repos/octocat/Hello-World/deployments",
            "description": "This your first repo!",
            "disabled": False,
            "downloads_url": "https://HOSTNAME/repos/octocat/Hello-World/downloads",
            "events_url": "https://HOSTNAME/repos/octocat/Hello-World/events",
            "fork": False,
            "forks_count": 9,
            "forks_url": "https://HOSTNAME/repos/octocat/Hello-World/forks",
            "full_name": "octocat/Hello-World",
            "git_commits_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/git/commits{/sha}"
            ),
            "git_refs_url": "https://HOSTNAME/repos/octocat/Hello-World/git/refs{/sha}",
            "git_tags_url": "https://HOSTNAME/repos/octocat/Hello-World/git/tags{/sha}",
            "git_url": "git:github.com/octocat/Hello-World.git",
            "has_discussions": False,
            "has_downloads": True,
            "has_issues": True,
            "has_pages": False,
            "has_projects": True,
            "has_wiki": True,
            "homepage": "https://github.com",
            "hooks_url": "https://HOSTNAME/repos/octocat/Hello-World/hooks",
            "html_url": "https://github.com/octocat/Hello-World",
            "id": 1296269,
            "is_template": False,
            "issue_comment_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/issues/comments{/number}"
            ),
            "issue_events_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/issues/events{/number}"
            ),
            "issues_url": "https://HOSTNAME/repos/octocat/Hello-World/issues{/number}",
            "keys_url": "https://HOSTNAME/repos/octocat/Hello-World/keys{/key_id}",
            "labels_url": "https://HOSTNAME/repos/octocat/Hello-World/labels{/name}",
            "language": None,
            "languages": [{"name": "Java"}, {"name": "OCaml"}],
            "languages_url": "https://HOSTNAME/repos/octocat/Hello-World/languages",
            "merges_url": "https://HOSTNAME/repos/octocat/Hello-World/merges",
            "milestones_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/milestones{/number}"
            ),
            "mirror_url": "git:git.example.com/octocat/Hello-World",
            "name": "Hello-World",
            "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
            "notifications_url": "https://HOSTNAME/repos/octocat/Hello-World/notifications{?since,all,participating}",
            "open_issues_count": 0,
            "owner_login": {
                "avatar_url": "https://github.com/images/error/octocat_happy.gif",
                "events_url": "https://HOSTNAME/users/octocat/events{/privacy}",
                "followers_url": "https://HOSTNAME/users/octocat/followers",
                "following_url": (
                    "https://HOSTNAME/users/octocat/following{/other_user}"
                ),
                "gists_url": "https://HOSTNAME/users/octocat/gists{/gist_id}",
                "gravatar_id": "",
                "html_url": "https://github.com/octocat",
                "id": 1,
                "login": "octocat",
                "node_id": "MDQ6VXNlcjE=",
                "organizations_url": "https://HOSTNAME/users/octocat/orgs",
                "received_events_url": "https://HOSTNAME/users/octocat/received_events",
                "repos_url": "https://HOSTNAME/users/octocat/repos",
                "site_admin": False,
                "starred_url": "https://HOSTNAME/users/octocat/starred{/owner}{/repo}",
                "subscriptions_url": "https://HOSTNAME/users/octocat/subscriptions",
                "type": "User",
                "url": "https://HOSTNAME/users/octocat",
            },
            "permissions": {"admin": False, "pull": True, "push": False},
            "private": False,
            "pulls_url": "https://HOSTNAME/repos/octocat/Hello-World/pulls{/number}",
            "pushed_at": "2011-01-26T19:06:43Z",
            "releases_url": "https://HOSTNAME/repos/octocat/Hello-World/releases{/id}",
            "security_and_analysis": {
                "advanced_security": {"status": "enabled"},
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "disabled"},
            },
            "size": 108,
            "ssh_url": "git@github.com:octocat/Hello-World.git",
            "stargazers_count": 80,
            "stargazers_url": "https://HOSTNAME/repos/octocat/Hello-World/stargazers",
            "statuses_url": "https://HOSTNAME/repos/octocat/Hello-World/statuses/{sha}",
            "subscribers_url": "https://HOSTNAME/repos/octocat/Hello-World/subscribers",
            "subscription_url": (
                "https://HOSTNAME/repos/octocat/Hello-World/subscription"
            ),
            "svn_url": "https://svn.github.com/octocat/Hello-World",
            "tags_url": "https://HOSTNAME/repos/octocat/Hello-World/tags",
            "teams_url": "https://HOSTNAME/repos/octocat/Hello-World/teams",
            "topics": ["octocat", "atom", "electron", "api"],
            "trees_url": "https://HOSTNAME/repos/octocat/Hello-World/git/trees{/sha}",
            "updated_at": "2011-01-26T19:14:43Z",
            "url": "https://HOSTNAME/repos/octocat/Hello-World",
            "visibility": "public",
            "watchers_count": 80,
            "webhooks": [{
                "active": True,
                "config": {
                    "content_type": "json",
                    "insecure_ssl": "0",
                    "url": "https://example.com/webhook",
                },
                "created_at": "2019-06-03T00:57:16Z",
                "deliveries_url": "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678/deliveries",
                "events": ["push", "pull_request"],
                "id": 12345678,
                "last_response": {"code": None, "message": None, "status": "unused"},
                "name": "web",
                "ping_url": (
                    "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678/pings"
                ),
                "test_url": (
                    "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678/test"
                ),
                "type": "Repository",
                "updated_at": "2019-06-03T00:57:16Z",
                "url": "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678",
            }],
        },
        {
            "archive_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/{archive_format}{/ref}"
            ),
            "archived": False,
            "assignees_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/assignees{/user}"
            ),
            "blobs_url": "https://HOSTNAME/repos/github/Hello-Moon/git/blobs{/sha}",
            "branches_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/branches{/branch}"
            ),
            "clone_url": "https://github.com/github/Hello-Moon.git",
            "collaborators": [{"id": 2, "login": "turbo", "node_id": "MDQ6VXNlcjI="}],
            "collaborators_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/collaborators{/collaborator}"
            ),
            "comments_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/comments{/number}"
            ),
            "commits_url": "https://HOSTNAME/repos/github/Hello-Moon/commits{/sha}",
            "compare_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/compare/{base}...{head}"
            ),
            "contents_url": "https://HOSTNAME/repos/github/Hello-Moon/contents/{+path}",
            "contributors_url": "https://HOSTNAME/repos/github/Hello-Moon/contributors",
            "created_at": "2011-01-26T19:01:12Z",
            "default_branch": "master",
            "deployments_url": "https://HOSTNAME/repos/github/Hello-Moon/deployments",
            "description": "This your first repo!",
            "disabled": False,
            "downloads_url": "https://HOSTNAME/repos/github/Hello-Moon/downloads",
            "events_url": "https://HOSTNAME/repos/github/Hello-Moon/events",
            "fork": False,
            "forks_count": 9,
            "forks_url": "https://HOSTNAME/repos/github/Hello-Moon/forks",
            "full_name": "github/Hello-Moon",
            "git_commits_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/git/commits{/sha}"
            ),
            "git_refs_url": "https://HOSTNAME/repos/github/Hello-Moon/git/refs{/sha}",
            "git_tags_url": "https://HOSTNAME/repos/github/Hello-Moon/git/tags{/sha}",
            "git_url": "git:github.com/github/Hello-Moon.git",
            "has_discussions": False,
            "has_downloads": True,
            "has_issues": True,
            "has_pages": False,
            "has_projects": True,
            "has_wiki": True,
            "homepage": "https://github.com",
            "hooks_url": "https://HOSTNAME/repos/github/Hello-Moon/hooks",
            "html_url": "https://github.com/github/Hello-Moon",
            "id": 1296269,
            "is_template": False,
            "issue_comment_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/issues/comments{/number}"
            ),
            "issue_events_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/issues/events{/number}"
            ),
            "issues_url": "https://HOSTNAME/repos/github/Hello-Moon/issues{/number}",
            "keys_url": "https://HOSTNAME/repos/github/Hello-Moon/keys{/key_id}",
            "labels_url": "https://HOSTNAME/repos/github/Hello-Moon/labels{/name}",
            "language": None,
            "languages": [{"name": "golang"}, {"name": "perl"}],
            "languages_url": "https://HOSTNAME/repos/github/Hello-Moon/languages",
            "merges_url": "https://HOSTNAME/repos/github/Hello-Moon/merges",
            "milestones_url": (
                "https://HOSTNAME/repos/github/Hello-Moon/milestones{/number}"
            ),
            "mirror_url": "git:git.example.com/github/Hello-Moon",
            "name": "Hello-Moon",
            "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
            "notifications_url": "https://HOSTNAME/repos/github/Hello-Moon/notifications{?since,all,participating}",
            "open_issues_count": 0,
            "permissions": {"admin": False, "pull": True, "push": False},
            "private": False,
            "pulls_url": "https://HOSTNAME/repos/github/Hello-Moon/pulls{/number}",
            "pushed_at": "2011-01-26T19:06:43Z",
            "releases_url": "https://HOSTNAME/repos/github/Hello-Moon/releases{/id}",
            "security_and_analysis": {
                "advanced_security": {"status": "enabled"},
                "secret_scanning": {"status": "enabled"},
                "secret_scanning_push_protection": {"status": "disabled"},
            },
            "size": 108,
            "ssh_url": "git@github.com:github/Hello-Moon.git",
            "stargazers_count": 80,
            "stargazers_url": "https://HOSTNAME/repos/github/Hello-Moon/stargazers",
            "statuses_url": "https://HOSTNAME/repos/github/Hello-Moon/statuses/{sha}",
            "subscribers_url": "https://HOSTNAME/repos/github/Hello-Moon/subscribers",
            "subscription_url": "https://HOSTNAME/repos/github/Hello-Moon/subscription",
            "svn_url": "https://svn.github.com/github/Hello-Moon",
            "tags_url": "https://HOSTNAME/repos/github/Hello-Moon/tags",
            "teams_url": "https://HOSTNAME/repos/github/Hello-Moon/teams",
            "topics": ["octocat", "atom", "electron", "api"],
            "trees_url": "https://HOSTNAME/repos/github/Hello-Moon/git/trees{/sha}",
            "updated_at": "2011-01-26T19:14:43Z",
            "url": "https://HOSTNAME/repos/github/Hello-Moon",
            "visibility": "public",
            "watchers_count": 80,
            "webhooks": [{
                "active": True,
                "config": {
                    "content_type": "json",
                    "insecure_ssl": "0",
                    "url": "https://example.com/webhook",
                },
                "created_at": "2019-06-03T00:57:16Z",
                "deliveries_url": "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678/deliveries",
                "events": ["push", "pull_request"],
                "id": 12345678,
                "last_response": {"code": None, "message": None, "status": "unused"},
                "name": "web",
                "ping_url": (
                    "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678/pings"
                ),
                "test_url": (
                    "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678/test"
                ),
                "type": "Repository",
                "updated_at": "2019-06-03T00:57:16Z",
                "url": "https://HOSTNAME/repos/octocat/Hello-World/hooks/12345678",
            }],
        },
    ]
