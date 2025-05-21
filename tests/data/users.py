from typing import Any

from nodestream_github.types import GithubUser
from tests.data.util import encode_as_node_id


def user_short(
    *,
    user_login: str = "octocat",
    user_id: int = 1,
    **kwargs: Any,
) -> GithubUser:

    return {
        "login": f"{user_login}",
        "id": user_id,
        "node_id": encode_as_node_id(f"04:User{user_id}"),
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": f"https://HOSTNAME/users/{user_login}",
        "html_url": f"https://github.com/{user_login}",
        "followers_url": f"https://HOSTNAME/users/{user_login}/followers",
        "following_url": (
            f"https://HOSTNAME/users/{user_login}/following{{/other_user}}"
        ),
        "gists_url": f"https://HOSTNAME/users/{user_login}/gists{{/gist_id}}",
        "starred_url": (
            f"https://HOSTNAME/users/{user_login}/starred{{/owner}}{{/repo}}"
        ),
        "subscriptions_url": f"https://HOSTNAME/users/{user_login}/subscriptions",
        "organizations_url": f"https://HOSTNAME/users/{user_login}/orgs",
        "repos_url": f"https://HOSTNAME/users/{user_login}/repos",
        "events_url": f"https://HOSTNAME/users/{user_login}/events{{/privacy}}",
        "received_events_url": f"https://HOSTNAME/users/{user_login}/received_events",
        "type": "User",
        "site_admin": False,
    } | kwargs


def user(
    *,
    user_login: str = "octocat",
    user_id: int = 1,
    **kwargs: Any,
) -> GithubUser:

    return (
        user_short(user_login=user_login, user_id=user_id)
        | {
            "name": "monalisa octocat",
            "company": "GitHub",
            "blog": "https://github.com/blog",
            "location": "San Francisco",
            "email": "octocat@github.com",
            "hireable": False,
            "bio": "There once was...",
            "twitter_username": "monatheoctocat",
            "public_repos": 2,
            "public_gists": 1,
            "followers": 20,
            "following": 0,
            "created_at": "2008-01-14T04:33:35Z",
            "updated_at": "2008-01-14T04:33:35Z",
        }
        | kwargs
    )


OCTOCAT_USER_SHORT = user_short(user_login="octocat")
TURBO_USER_SHORT = user_short(user_login="turbo", user_id=2)

OCTOCAT_USER = user_short(user_login="octocat")
TURBO_USER = user_short(user_login="turbo", user_id=2)
