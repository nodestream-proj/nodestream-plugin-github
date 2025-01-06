from tests.data.util import encode_as_node_id


def org_summary(login="github", org_id=1, **kwargs):
    return {
        "login": login,
        "id": org_id,
        "node_id": encode_as_node_id(f"012:Organization{org_id}"),
        "url": "https://HOSTNAME/orgs/github",
        "repos_url": f"https://HOSTNAME/orgs/{login}/repos",
        "events_url": f"https://HOSTNAME/orgs/{login}/events",
        "hooks_url": f"https://HOSTNAME/orgs/{login}/hooks",
        "issues_url": f"https://HOSTNAME/orgs/{login}/issues",
        "members_url": f"https://HOSTNAME/orgs/{login}/members{{/member}}",
        "public_members_url": (
            f"https://HOSTNAME/orgs/{login}/public_members{{/member}}"
        ),
        "avatar_url": "https://github.com/images/error/octocat_happy.gif",
        "description": "A great organization",
    } | kwargs


def org(login="github", org_id=1, **kwargs):
    summary = org_summary(login, org_id)
    login = summary["login"]
    return (
        summary
        | {
            "name": login,
            "company": login,
            "blog": f"https://{login}.com/blog",
            "location": "San Francisco",
            "email": f"octocat@{login}.com",
            "twitter_username": "github",
            "is_verified": True,
            "has_organization_projects": True,
            "has_repository_projects": True,
            "public_repos": 2,
            "public_gists": 1,
            "followers": 20,
            "following": 0,
            "html_url": f"https://github.com/{login}",
            "created_at": "2008-01-14T04:33:35Z",
            "type": "Organization",
            "total_private_repos": 100,
            "owned_private_repos": 100,
            "private_gists": 81,
            "disk_usage": 10000,
            "collaborators": 8,
            "billing_email": f"mona@{login}.com",
            "plan": {
                "name": "Medium",
                "space": 400,
                "private_repos": 20,
                "filled_seats": 4,
                "seats": 5,
            },
            "default_repository_permission": "read",
            "members_can_create_repositories": True,
            "two_factor_requirement_enabled": True,
            "members_allowed_repository_creation_type": "all",
            "members_can_create_public_repositories": False,
            "members_can_create_private_repositories": False,
            "members_can_create_internal_repositories": False,
            "members_can_create_pages": True,
            "members_can_create_public_pages": True,
            "members_can_create_private_pages": True,
            "members_can_fork_private_repositories": False,
            "web_commit_signoff_required": False,
            "updated_at": "2014-03-03T18:58:10Z",
            "dependency_graph_enabled_for_new_repositories": False,
            "dependabot_alerts_enabled_for_new_repositories": False,
            "dependabot_security_updates_enabled_for_new_repositories": False,
            "advanced_security_enabled_for_new_repositories": False,
            "secret_scanning_enabled_for_new_repositories": False,
            "secret_scanning_push_protection_enabled_for_new_repositories": False,
            "secret_scanning_push_protection_custom_link": (
                "https://github.com/octo-org/octo-repo/blob/main/im-blocked.md"
            ),
            "secret_scanning_push_protection_custom_link_enabled": False,
        }
        | kwargs
    )


GITHUB_ORG_SUMMARY = org_summary()
GITHUB_ORG = org()
EXAMPLE_ORG_SUMMARY = org_summary(login="example", org_id=2)
EXAMPLE_ORG = org(login="example", org_id=2)
