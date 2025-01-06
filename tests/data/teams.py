from tests.data.orgs import GITHUB_ORG
from tests.data.util import encode_as_node_id


def team_summary(team_id=1, slug="justice-league", org_login="github", **kwargs):
    return {
        "id": team_id,
        "node_id": encode_as_node_id(f"04:Team{team_id}"),
        "url": f"https://HOSTNAME/teams/{team_id}",
        "html_url": f"https://github.com/orgs/{org_login}/teams/{slug}",
        "name": "Justice League",
        "slug": slug,
        "description": "A great team.",
        "privacy": "closed",
        "notification_setting": "notifications_enabled",
        "permission": "admin",
        "members_url": f"https://HOSTNAME/teams/{team_id}/members{{/member}}",
        "repositories_url": f"https://HOSTNAME/teams/{team_id}/repos",
        "parent": None,
    } | kwargs


def team(team_id=1, organization=None, slug="justice-league", **kwargs):
    org = GITHUB_ORG if not organization else organization
    summary = team_summary(team_id=team_id, org_login=org["login"], slug=slug)
    return (
        summary
        | {
            "members_count": 3,
            "repos_count": 10,
            "created_at": "2017-07-14T16:53:42Z",
            "updated_at": "2017-08-17T12:37:15Z",
            "organization": org,
            "ldap_dn": "uid=asdf,ou=users,dc=github,dc=com",
        }
        | kwargs
    )


JUSTICE_LEAGUE_TEAM_SUMMARY = team_summary()
JUSTICE_LEAGUE_TEAM = team()
