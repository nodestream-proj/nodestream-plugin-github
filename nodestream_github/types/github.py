from typing import TypeAlias

JSONType: TypeAlias = (
    dict[str, "JSONType"] | list["JSONType"] | str | int | float | bool | None
)
JSONObject: TypeAlias = dict[str, JSONType]

GithubOrgSummary: TypeAlias = JSONObject
GithubOrg: TypeAlias = JSONObject
GithubRepo: TypeAlias = JSONObject
GithubUser: TypeAlias = JSONObject
Webhook: TypeAlias = JSONObject
GithubTeam: TypeAlias = JSONObject
GithubTeamSummary: TypeAlias = JSONObject
GithubAuditLog: TypeAlias = JSONObject

LanguageRecord: TypeAlias = JSONObject
OrgRecord: TypeAlias = JSONObject
RepositoryRecord: TypeAlias = JSONObject
TeamRecord: TypeAlias = JSONObject
UserRecord: TypeAlias = JSONObject

SimplifiedRepo: TypeAlias = JSONObject
SimplifiedUser: TypeAlias = JSONObject
