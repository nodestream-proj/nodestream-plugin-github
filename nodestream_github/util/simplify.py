"""simplify

A collection of utility functions for simplifying GitHub objects in a consistent
way for relationship interpretations.
"""


def simplify_user(user):
    """Simplify user data.

    Allows us to only keep the bare-minimum to avoid memory overruns."""
    data = {
        "id": user["id"],
        "login": user["login"],
        "node_id": user["node_id"],
    }
    if "role" in user:
        data["role"] = user["role"]
    if "permissions" in user:
        data["permissions"] = user["permissions"]
    return data


def simplify_repo(repo):
    """Simplify repo data.

    Allows us to only keep the bare-minimum to avoid memory overruns."""
    data = {
        "id": repo["id"],
        "node_id": repo["node_id"],
        "name": repo["name"],
        "full_name": repo["full_name"],
        "url": repo["url"],
    }
    if "permissions" in repo:
        data["permissions"] = repo["permissions"]
    return data
