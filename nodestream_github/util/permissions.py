from enum import StrEnum


class PermissionName(StrEnum):
    METADATA = "Metadata"
    WEBHOOKS = "Webhooks"
    MEMBERS = "Members"


class PermissionCategory(StrEnum):
    REPO = "repository"
    ORG = "organization"
