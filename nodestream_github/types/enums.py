from enum import StrEnum


class CollaboratorAffiliation(StrEnum):
    ALL = "all"
    OUTSIDE = "outside"
    DIRECT = "direct"


class OrgRepoType(StrEnum):
    ALL = "all"
    PUBLIC = "public"
    PRIVATE = "private"
    FORKS = "forks"
    SOURCES = "sources"
    MEMBER = "member"
    INTERNAL = "internal"


class UserRepoType(StrEnum):
    ALL = "all"
    OWNER = "owner"
    MEMBER = "member"


class OrgMemberRole(StrEnum):
    ALL = "all"
    ADMIN = "admin"
    MEMBER = "member"


class TeamMemberRole(StrEnum):
    ALL = "all"
    MAINTAINER = "maintainer"
    MEMBER = "member"
