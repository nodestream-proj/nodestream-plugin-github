# noinspection PyProtectedMember
from httpx._types import HeaderTypes
from pytest_httpx import HTTPXMock

DEFAULT_ENDPOINT = "https://test-example.githhub.intuit.com"
DEFAULT_PER_PAGE = 100


class GithubHttpxMock:
    def __init__(
        self,
        httpx_mock: HTTPXMock,
        endpoint: str = DEFAULT_ENDPOINT,
        per_page: int = 100,
    ):
        self._httpx_mock = httpx_mock
        self._endpoint = endpoint
        self._per_page = per_page

    @property
    def endpoint(self):
        return self._endpoint

    @property
    def per_page(self):
        return self._per_page

    @property
    def httpx_mock(self):
        return self._httpx_mock

    def add_exception(self, exception: Exception, **matchers: any):
        self.httpx_mock.add_exception(exception, **matchers)

    def add_response(
        self,
        status_code: int = 200,
        http_version: str = "HTTP/1.1",
        headers: HeaderTypes | None = None,
        content: bytes | None = None,
        text: str | None = None,
        html: str | None = None,
        stream: any = None,
        json: any = None,
        **matchers: any,
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

    def all_orgs(self, **kwargs) -> None:
        self.add_response(
            url=f"{self.endpoint}/organizations?per_page={self.per_page}", **kwargs
        )

    def get_org(self, org_name: str, **kwargs) -> None:
        self.add_response(url=f"{self.endpoint}/orgs/{org_name}", **kwargs)

    def get_members_for_org(
        self, org_name: str, role: str | None = None, **kwargs
    ) -> None:
        actual_role = f"role={role}" if role else ""
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_name}/members?per_page={self.per_page}&{actual_role}",
            **kwargs,
        )

    def get_repos_for_org(self, org_name: str, repo_type: str | None = None, **kwargs):
        type_param = f"&type={repo_type}" if repo_type else ""
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_name}/repos?per_page={self.per_page}{type_param}",
            **kwargs,
        )

    def list_teams_for_org(self, org_login: str, **kwargs):
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_login}/teams?per_page={self.per_page}",
            **kwargs,
        )

    def get_team(self, org_login: str, team_slug: str, **kwargs):
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_login}/teams/{team_slug}", **kwargs
        )

    def get_members_for_team(self, team_id: int, role: str, **kwargs):
        self.add_response(
            url=f"{self.endpoint}/teams/{team_id}/members?per_page={self.per_page}&role={role}",
            **kwargs,
        )

    def get_repos_for_team(self, team_id: int, **kwargs):
        self.add_response(
            url=f"{self.endpoint}/teams/{team_id}/repos?per_page={self.per_page}",
            **kwargs,
        )

    def all_repos(self, **kwargs) -> None:
        self.add_response(
            url=f"{self.endpoint}/repositories?per_page={self.per_page}", **kwargs
        )

    def get_languages_for_repo(
        self, owner_login: str, repo_name: str, **kwargs
    ) -> None:
        self.add_response(
            url=f"{self.endpoint}/repos/{owner_login}/{repo_name}/languages?per_page={self.per_page}",
            **kwargs,
        )

    def get_webhooks_for_repo(self, owner_login: str, repo_name: str, **kwargs) -> None:
        self.add_response(
            url=f"{self.endpoint}/repos/{owner_login}/{repo_name}/webhooks?per_page={self.per_page}",
            **kwargs,
        )

    def get_collaborators_for_repo(
        self, owner_login: str, repo_name: str, **kwargs
    ) -> None:
        self.add_response(
            url=f"{self.endpoint}/repos/{owner_login}/{repo_name}/collaborators?per_page={self.per_page}",
            **kwargs,
        )

    def all_users(self, **kwargs):
        self.add_response(
            url=f"{self.endpoint}/users?per_page={self.per_page}", **kwargs
        )

    def get_repos_for_user(self, user_login: str, type_param: str | None, **kwargs):
        type_param = f"&type={type_param}" if type_param else ""
        self.add_response(
            url=f"{self.endpoint}/users/{user_login}/repos?per_page=100&{type_param}",
            **kwargs,
        )
