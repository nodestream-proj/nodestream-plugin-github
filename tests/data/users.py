from tests.data.util import encode_as_node_id


def user(login="octocat", user_id=1, **kwargs):

    return {
        "login": f"{login}",
        "id": user_id,
        "node_id": encode_as_node_id(f"04:User{user_id}"),
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "gravatar_id": "",
        "url": f"https://HOSTNAME/users/{login}",
        "html_url": f"https://github.com/{login}",
        "followers_url": f"https://HOSTNAME/users/{login}/followers",
        "following_url": f"https://HOSTNAME/users/{login}/following{{/other_user}}",
        "gists_url": f"https://HOSTNAME/users/{login}/gists{{/gist_id}}",
        "starred_url": f"https://HOSTNAME/users/{login}/starred{{/owner}}{{/repo}}",
        "subscriptions_url": f"https://HOSTNAME/users/{login}/subscriptions",
        "organizations_url": f"https://HOSTNAME/users/{login}/orgs",
        "repos_url": f"https://HOSTNAME/users/{login}/repos",
        "events_url": f"https://HOSTNAME/users/{login}/events{{/privacy}}",
        "received_events_url": f"https://HOSTNAME/users/{login}/received_events",
        "type": "User",
        "site_admin": False,
    } | kwargs


OCTOCAT_USER = user(login="octocat")
TURBO_USER = user(login="turbo", user_id=2)
