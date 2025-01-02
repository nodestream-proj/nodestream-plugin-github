from typing import AsyncGenerator

import pytest
from pytest_httpx import HTTPXMock

from nodestream_github import GithubUserExtractor

OCTOCAT_USER = {
    "login": "octocat",
    "id": 1,
    "node_id": "MDQ6VXNlcjE=",
    "avatar_url": "https://github.com/images/error/octocat_happy.gif",
    "gravatar_id": "",
    "url": "https://HOSTNAME/users/octocat",
    "html_url": "https://github.com/octocat",
    "followers_url": "https://HOSTNAME/users/octocat/followers",
    "following_url": "https://HOSTNAME/users/octocat/following{/other_user}",
    "gists_url": "https://HOSTNAME/users/octocat/gists{/gist_id}",
    "starred_url": "https://HOSTNAME/users/octocat/starred{/owner}{/repo}",
    "subscriptions_url": "https://HOSTNAME/users/octocat/subscriptions",
    "organizations_url": "https://HOSTNAME/users/octocat/orgs",
    "repos_url": "https://HOSTNAME/users/octocat/repos",
    "events_url": "https://HOSTNAME/users/octocat/events{/privacy}",
    "received_events_url": "https://HOSTNAME/users/octocat/received_events",
    "type": "User",
    "site_admin": False,
}

HELLO_WORLD_REPO = {
    "id": 1296269,
    "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
    "name": "Hello-World",
    "full_name": "octocat/Hello-World",
    "owner": {
        "login": "octocat",
        "id": 1,
        "node_id": "MDQ6VXNlcjE=",
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": "https://HOSTNAME/users/octocat",
        "html_url": "https://github.com/octocat",
        "followers_url": "https://HOSTNAME/users/octocat/followers",
        "following_url": "https://HOSTNAME/users/octocat/following{/other_user}",
        "gists_url": "https://HOSTNAME/users/octocat/gists{/gist_id}",
        "starred_url": "https://HOSTNAME/users/octocat/starred{/owner}{/repo}",
        "subscriptions_url": "https://HOSTNAME/users/octocat/subscriptions",
        "organizations_url": "https://HOSTNAME/users/octocat/orgs",
        "repos_url": "https://HOSTNAME/users/octocat/repos",
        "events_url": "https://HOSTNAME/users/octocat/events{/privacy}",
        "received_events_url": "https://HOSTNAME/users/octocat/received_events",
        "type": "User",
        "site_admin": False,
    },
    "private": False,
    "html_url": "https://github.com/octocat/Hello-World",
    "description": "This your first repo!",
    "fork": False,
    "url": "https://HOSTNAME/repos/octocat/Hello-World",
    "archive_url": "https://HOSTNAME/repos/octocat/Hello-World/{archive_format}{/ref}",
    "assignees_url": "https://HOSTNAME/repos/octocat/Hello-World/assignees{/user}",
    "blobs_url": "https://HOSTNAME/repos/octocat/Hello-World/git/blobs{/sha}",
    "branches_url": "https://HOSTNAME/repos/octocat/Hello-World/branches{/branch}",
    "collaborators_url": "https://HOSTNAME/repos/octocat/Hello-World/collaborators{/collaborator}",
    "comments_url": "https://HOSTNAME/repos/octocat/Hello-World/comments{/number}",
    "commits_url": "https://HOSTNAME/repos/octocat/Hello-World/commits{/sha}",
    "compare_url": "https://HOSTNAME/repos/octocat/Hello-World/compare/{base}...{head}",
    "contents_url": "https://HOSTNAME/repos/octocat/Hello-World/contents/{+path}",
    "contributors_url": "https://HOSTNAME/repos/octocat/Hello-World/contributors",
    "deployments_url": "https://HOSTNAME/repos/octocat/Hello-World/deployments",
    "downloads_url": "https://HOSTNAME/repos/octocat/Hello-World/downloads",
    "events_url": "https://HOSTNAME/repos/octocat/Hello-World/events",
    "forks_url": "https://HOSTNAME/repos/octocat/Hello-World/forks",
    "git_commits_url": "https://HOSTNAME/repos/octocat/Hello-World/git/commits{/sha}",
    "git_refs_url": "https://HOSTNAME/repos/octocat/Hello-World/git/refs{/sha}",
    "git_tags_url": "https://HOSTNAME/repos/octocat/Hello-World/git/tags{/sha}",
    "git_url": "git:github.com/octocat/Hello-World.git",
    "issue_comment_url": "https://HOSTNAME/repos/octocat/Hello-World/issues/comments{/number}",
    "issue_events_url": "https://HOSTNAME/repos/octocat/Hello-World/issues/events{/number}",
    "issues_url": "https://HOSTNAME/repos/octocat/Hello-World/issues{/number}",
    "keys_url": "https://HOSTNAME/repos/octocat/Hello-World/keys{/key_id}",
    "labels_url": "https://HOSTNAME/repos/octocat/Hello-World/labels{/name}",
    "languages_url": "https://HOSTNAME/repos/octocat/Hello-World/languages",
    "merges_url": "https://HOSTNAME/repos/octocat/Hello-World/merges",
    "milestones_url": "https://HOSTNAME/repos/octocat/Hello-World/milestones{/number}",
    "notifications_url": "https://HOSTNAME/repos/octocat/Hello-World/notifications{?since,all,participating}",
    "pulls_url": "https://HOSTNAME/repos/octocat/Hello-World/pulls{/number}",
    "releases_url": "https://HOSTNAME/repos/octocat/Hello-World/releases{/id}",
    "ssh_url": "git@github.com:octocat/Hello-World.git",
    "stargazers_url": "https://HOSTNAME/repos/octocat/Hello-World/stargazers",
    "statuses_url": "https://HOSTNAME/repos/octocat/Hello-World/statuses/{sha}",
    "subscribers_url": "https://HOSTNAME/repos/octocat/Hello-World/subscribers",
    "subscription_url": "https://HOSTNAME/repos/octocat/Hello-World/subscription",
    "tags_url": "https://HOSTNAME/repos/octocat/Hello-World/tags",
    "teams_url": "https://HOSTNAME/repos/octocat/Hello-World/teams",
    "trees_url": "https://HOSTNAME/repos/octocat/Hello-World/git/trees{/sha}",
    "clone_url": "https://github.com/octocat/Hello-World.git",
    "mirror_url": "git:git.example.com/octocat/Hello-World",
    "hooks_url": "https://HOSTNAME/repos/octocat/Hello-World/hooks",
    "svn_url": "https://svn.github.com/octocat/Hello-World",
    "homepage": "https://github.com",
    "language": None,
    "forks_count": 9,
    "stargazers_count": 80,
    "watchers_count": 80,
    "size": 108,
    "default_branch": "master",
    "open_issues_count": 0,
    "is_template": False,
    "topics": ["octocat", "atom", "electron", "api"],
    "has_issues": True,
    "has_projects": True,
    "has_wiki": True,
    "has_pages": False,
    "has_downloads": True,
    "has_discussions": False,
    "archived": False,
    "disabled": False,
    "visibility": "public",
    "pushed_at": "2011-01-26T19:06:43Z",
    "created_at": "2011-01-26T19:01:12Z",
    "updated_at": "2011-01-26T19:14:43Z",
    "permissions": {"admin": False, "push": False, "pull": True},
    "security_and_analysis": {
        "advanced_security": {"status": "enabled"},
        "secret_scanning": {"status": "enabled"},
        "secret_scanning_push_protection": {"status": "disabled"},
    },
}


@pytest.fixture
def user_client():
    return GithubUserExtractor(
        auth_token="test-token",
        github_endpoint="https://test-example.githhub.intuit.com",
        user_agent="test-agent",
        max_retries=0,
    )


async def to_list(async_generator: AsyncGenerator) -> list:
    output = []
    async for item in async_generator:
        output.append(item)
    return output


@pytest.mark.asyncio
async def test_github_user_extractor(user_client, httpx_mock: HTTPXMock):

    httpx_mock.add_response(
        status_code=200,
        url="https://test-example.githhub.intuit.com/users?per_page=100",
        json=[OCTOCAT_USER],
    )
    httpx_mock.add_response(
        status_code=200,
        url="https://test-example.githhub.intuit.com/users/octocat/repos?per_page=100&type=all",
        json=[HELLO_WORLD_REPO],
    )

    actual = await to_list(user_client.extract_records())

    assert actual == [
        OCTOCAT_USER
        | {
            "repos": [
                {
                    "full_name": "octocat/Hello-World",
                    "id": 1296269,
                    "name": "Hello-World",
                    "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                    "permissions": {"admin": False, "pull": True, "push": False},
                    "url": "https://HOSTNAME/repos/octocat/Hello-World",
                }
            ]
        }
    ]
