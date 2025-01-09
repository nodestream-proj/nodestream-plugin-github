from typing import TypeAlias

JSONType: TypeAlias = (
    dict[str, "JSONType"] | list["JSONType"] | str | int | float | bool | None
)

GithubOrgSummary: TypeAlias = JSONType
GithubOrg: TypeAlias = JSONType
GithubRepo: TypeAlias = JSONType
GithubUser: TypeAlias = JSONType
Webhook: TypeAlias = JSONType
GithubTeam: TypeAlias = JSONType
GithubTeamSummary: TypeAlias = JSONType

LanguageRecord: TypeAlias = JSONType
OrgRecord: TypeAlias = JSONType
RepositoryRecord: TypeAlias = JSONType
TeamRecord: TypeAlias = JSONType
UserRecord: TypeAlias = JSONType

SimplifiedRepo: TypeAlias = JSONType
SimplifiedUser: TypeAlias = JSONType
