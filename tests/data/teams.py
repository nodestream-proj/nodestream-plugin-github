from typing import Unpack

from nodestream_github.types.gh_model import (
    OrganizationFull,
    Team,
    TeamFull,
    TeamOrganization,
)
from tests.data.orgs import GITHUB_ORG
from tests.data.util import encode_as_node_id


def team_summary(
    *,
    team_id: int = 1,
    org_login: str = "github",
    **kwargs: Unpack[Team],
) -> Team:
    slug = kwargs.get("slug", "justice-league")
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


def team(
    *,
    team_id: int = 1,
    org: OrganizationFull | None = None,
    **kwargs: Unpack[TeamFull],
) -> TeamFull:
    _org = TeamOrganization(**(org or GITHUB_ORG))  # ty: ignore[invalid-key]

    summary = team_summary(
        team_id=team_id,
        org_login=_org["login"],
        slug=kwargs.get("slug", "justice-league"),
    )
    _summary = {**summary}
    output = TeamFull(**_summary)
    output.update({
        "members_count": 3,
        "repos_count": 10,
        "created_at": "2017-07-14T16:53:42Z",
        "updated_at": "2017-08-17T12:37:15Z",
        "organization": _org,
        "ldap_dn": "uid=asdf,ou=users,dc=github,dc=com",
    })
    output.update(**kwargs)
    return output


JUSTICE_LEAGUE_TEAM_SUMMARY = team_summary()
JUSTICE_LEAGUE_TEAM = team()
