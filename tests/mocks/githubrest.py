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

    def all_orgs(self, json: list[dict[str, any]], status_code: int = 200) -> None:
        self.add_response(
            status_code=status_code,
            url=f"{self.endpoint}/organizations?per_page={self.per_page}",
            json=json,
        )

    def get_org(
        self, org_name: str, json: dict[str, any] = None, status_code: int = 200
    ) -> None:
        self.add_response(
            status_code=status_code,
            url=f"{self.endpoint}/orgs/{org_name}",
            json=json,
        )

    def get_members_for_org(
        self,
        org_name: str,
        json: list[dict[str, any]],
        status_code: int = 200,
        role: str = None,
    ) -> None:
        actual_role = f"role={role}" if role else ""
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_name}/members?per_page={self.per_page}&{actual_role}",
            status_code=status_code,
            json=json,
        )

    def get_repos_for_org(
        self, org_name: str, json: list[dict[str, any]], status_code: int = 200
    ):
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_name}/repos?per_page={self.per_page}",
            status_code=status_code,
            json=json,
        )

    def list_teams_for_org(self, org_login: str, json: list[dict[str, any]]):
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_login}/teams?per_page={self.per_page}",
            json=json,
        )

    def get_team(self, org_login: str, team_slug: str, json):
        self.add_response(
            url=f"{self.endpoint}/orgs/{org_login}/teams/{team_slug}",
            json=json,
        )

    def get_members_for_team(self, team_id: int, role: str, json: list[dict[str, any]]):
        self.add_response(
            url=f"{self.endpoint}/teams/{team_id}/members?per_page={self.per_page}&role={role}",
            json=json,
        )

    def get_repos_for_team(self, team_id: int, json: list[dict[str, any]]):
        self.add_response(
            url=f"{self.endpoint}/teams/{team_id}/repos?per_page={self.per_page}",
            json=json,
        )

    def all_repos(self, json: list[dict[str, any]], status_code: int = 200) -> None:
        self.add_response(
            url=f"{self.endpoint}/repositories?per_page={self.per_page}",
            json=json,
            status_code=status_code,
        )

    def get_languages_for_repo(
        self, owner_login: str, repo_name: str, json: list[str], status_code: int = 200
    ) -> None:
        self.add_response(
            url=f"{self.endpoint}/repos/{owner_login}/{repo_name}/languages?per_page={self.per_page}",
            json=json,
            status_code=status_code,
        )

    def get_webhooks_for_repo(
        self,
        owner_login: str,
        repo_name: str,
        json: list[dict[str, any]],
        status_code: int = 200,
    ) -> None:
        self.add_response(
            url=f"{self.endpoint}/repos/{owner_login}/{repo_name}/webhooks?per_page={self.per_page}",
            json=json,
            status_code=status_code,
        )

    def get_collaborators_for_repo(
        self,
        owner_login: str,
        repo_name: str,
        json: list[dict[str, any]],
        status_code: int = 200,
    ) -> None:
        self.add_response(
            url=f"{self.endpoint}/repos/{owner_login}/{repo_name}/collaborators?per_page={self.per_page}",
            json=json,
            status_code=status_code,
        )
