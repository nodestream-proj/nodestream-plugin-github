from nodestream_github.types import GithubRepo
from tests.data.users import OCTOCAT_USER
from tests.data.util import encode_as_node_id


def repo(
    owner: dict[str, any] | None = None,
    repo_name: str = "Hello-World",
    repo_id: int = 1296269,
    **kwargs: any,
) -> GithubRepo:

    repo_owner = OCTOCAT_USER if owner is None else owner
    owner_login = repo_owner["login"]

    return {
        "id": repo_id,
        "node_id": encode_as_node_id(f"010:Repository{repo_id}"),
        "name": repo_name,
        "full_name": f"{owner_login}/{repo_name}",
        "owner": repo_owner,
        "private": False,
        "html_url": f"https://github.com/{owner_login}/{repo_name}",
        "description": "This your first repo!",
        "fork": False,
        "url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}",
        "archive_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/{{archive_format}}{{/ref}}",
        "assignees_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/assignees{{/user}}"
        ),
        "blobs_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/git/blobs{{/sha}}"
        ),
        "branches_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/branches{{/branch}}"
        ),
        "collaborators_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/collaborators{{/collaborator}}",
        "comments_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/comments{{/number}}"
        ),
        "commits_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/commits{{/sha}}"
        ),
        "compare_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/compare/{{base}}...{{head}}",
        "contents_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/contents/{{+path}}"
        ),
        "contributors_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/contributors"
        ),
        "deployments_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/deployments"
        ),
        "downloads_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/downloads",
        "events_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/events",
        "forks_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/forks",
        "git_commits_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/git/commits{{/sha}}"
        ),
        "git_refs_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/git/refs{{/sha}}"
        ),
        "git_tags_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/git/tags{{/sha}}"
        ),
        "git_url": f"git:github.com/{owner_login}/{repo_name}.git",
        "issue_comment_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/issues/comments{{/number}}",
        "issue_events_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/issues/events{{/number}}"
        ),
        "issues_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/issues{{/number}}"
        ),
        "keys_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/keys{{/key_id}}",
        "labels_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/labels{{/name}}"
        ),
        "languages_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/languages",
        "merges_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/merges",
        "milestones_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/milestones{{/number}}"
        ),
        "notifications_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/notifications{{?since,all,participating}}",
        "pulls_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/pulls{{/number}}"
        ),
        "releases_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/releases{{/id}}"
        ),
        "ssh_url": f"git@github.com:{owner_login}/{repo_name}.git",
        "stargazers_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/stargazers"
        ),
        "statuses_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/statuses/{{sha}}"
        ),
        "subscribers_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/subscribers"
        ),
        "subscription_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/subscription"
        ),
        "tags_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/tags",
        "teams_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/teams",
        "trees_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/git/trees{{/sha}}"
        ),
        "clone_url": f"https://github.com/{owner_login}/{repo_name}.git",
        "mirror_url": f"git:git.example.com/{owner_login}/{repo_name}",
        "hooks_url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/hooks",
        "svn_url": f"https://svn.github.com/{owner_login}/{repo_name}",
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
    } | kwargs


HELLO_WORLD_REPO = repo(owner=OCTOCAT_USER, repo_name="Hello-World")
