# noinspection PyProtectedMember
from typing import Any

from pytest_httpx import HTTPXMock

from nodestream_github.types import HeaderTypes
from nodestream_github.types.enums import (
    CollaboratorAffiliation,
    OrgMemberRole,
    OrgRepoType,
    TeamMemberRole,
    UserRepoType,
)

DEFAULT_HOSTNAME = "test-example.github.intuit.com"
DEFAULT_BASE_URL = f"https://{DEFAULT_HOSTNAME}/api/v3"

DEFAULT_PER_PAGE = 100


class GithubHttpxMock:
    def __init__(
        self,
        httpx_mock: HTTPXMock,
        base_url: str = DEFAULT_BASE_URL,
        per_page: int = 100,
    ):
        self._httpx_mock = httpx_mock
        self._base_url = base_url
        self._per_page = per_page

    @property
    def base_url(self) -> str:
        return self._base_url

    @property
    def per_page(self) -> int:
        return self._per_page

    @property
    def httpx_mock(self) -> HTTPXMock:
        return self._httpx_mock

    def add_exception(self, *, exception: Exception, **matchers: Any):
        self.httpx_mock.add_exception(exception, **matchers)

    def add_response(
        self,
        *,
        status_code: int = 200,
        http_version: str = "HTTP/1.1",
        headers: HeaderTypes | None = None,
        content: bytes | None = None,
        text: str | None = None,
        html: str | None = None,
        stream: Any = None,  # noqa ANN401
        json: Any = None,  # noqa ANN401
        **matchers: Any,
    ):
        self.httpx_mock.add_response(
            status_code=status_code,
            http_version=http_version,
            headers=headers,
            content=content,
            text=text,
            html=html,
            stream=stream,
            json=json,
            **matchers,
        )

    def all_orgs(self, **kwargs: Any) -> None:
        self.add_response(
            url=f"{self.base_url}/organizations?per_page={self.per_page}", **kwargs
        )

    def get_org(self, *, org_name: str, **kwargs: Any) -> None:
        self.add_response(url=f"{self.base_url}/orgs/{org_name}", **kwargs)

    def get_members_for_org(
        self,
        *,
        org_name: str,
        role: OrgMemberRole | None = None,
        **kwargs: Any,
    ) -> None:
        actual_role = f"role={role}" if role else ""
        self.add_response(
            url=f"{self.base_url}/orgs/{org_name}/members?per_page={self.per_page}&{actual_role}",
            **kwargs,
        )

    def get_repos_for_org(
        self,
        *,
        org_name: str,
        repo_type: OrgRepoType | None = None,
        **kwargs: Any,
    ):
        type_param = f"&type={repo_type}" if repo_type else ""
        self.add_response(
            url=f"{self.base_url}/orgs/{org_name}/repos?per_page={self.per_page}{type_param}",
            **kwargs,
        )

    def list_teams_for_org(self, *, org_login: str, **kwargs: Any):
        self.add_response(
            url=f"{self.base_url}/orgs/{org_login}/teams?per_page={self.per_page}",
            **kwargs,
        )

    def get_team(self, *, org_login: str, team_slug: str, **kwargs: Any):
        self.add_response(
            url=f"{self.base_url}/orgs/{org_login}/teams/{team_slug}", **kwargs
        )

    def get_members_for_team(
        self,
        *,
        team_id: int,
        role: TeamMemberRole,
        **kwargs: Any,
    ):
        self.add_response(
            url=f"{self.base_url}/teams/{team_id}/members?per_page={self.per_page}&role={role}",
            **kwargs,
        )

    def get_repos_for_team(self, *, org_login: str, slug: str, **kwargs: Any):
        self.add_response(
            url=f"{self.base_url}/orgs/{org_login}/teams/{slug}/repos?per_page={self.per_page}",
            **kwargs,
        )

    def all_repos(self, **kwargs: Any) -> None:
        self.add_response(
            url=f"{self.base_url}/repositories?per_page={self.per_page}", **kwargs
        )

    def get_languages_for_repo(
        self,
        *,
        owner_login: str,
        repo_name: str,
        **kwargs: Any,
    ) -> None:
        self.add_response(
            url=f"{self.base_url}/repos/{owner_login}/{repo_name}/languages?per_page={self.per_page}",
            **kwargs,
        )

    def get_webhooks_for_repo(self, *, owner_login: str, repo_name: str, **kwargs: Any):
        self.add_response(
            url=f"{self.base_url}/repos/{owner_login}/{repo_name}/hooks?per_page={self.per_page}",
            **kwargs,
        )

    def get_collaborators_for_repo(
        self,
        *,
        owner_login: str,
        repo_name: str,
        affiliation: CollaboratorAffiliation,
        **kwargs: Any,
    ) -> None:
        self.add_response(
            url=f"{self.base_url}/repos/{owner_login}/{repo_name}/collaborators?per_page={self.per_page}&affiliation={affiliation}",
            **kwargs,
        )

    def all_users(self, **kwargs: Any):
        self.add_response(
            url=f"{self.base_url}/users?per_page={self.per_page}", **kwargs
        )

    def get_user(self, *, username: str, **kwargs: Any):
        self.add_response(
            url=f"{self.base_url}/users/{username}",
            **kwargs,
        )

    def get_repos_for_user(
        self,
        *,
        user_login: str,
        type_param: UserRepoType | None,
        **kwargs: Any,
    ):
        type_param = f"&type={type_param}" if type_param else ""
        self.add_response(
            url=f"{self.base_url}/users/{user_login}/repos?per_page=100&{type_param}",
            **kwargs,
        )

    def get_enterprise_audit_logs(self, **kwargs: Any):
        url = (
            f"{self.base_url}/enterprises/test-enterprise"
            f"/audit-log?per_page=100&phrase=action:protected_branch.create"
        )
        self.add_response(url=url, **kwargs)
