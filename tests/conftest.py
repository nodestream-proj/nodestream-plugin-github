import pytest
from pytest_httpx import HTTPXMock

from tests.mocks.githubrest import GithubHttpxMock


@pytest.fixture
def gh_rest_mock(httpx_mock: HTTPXMock) -> GithubHttpxMock:
    return GithubHttpxMock(httpx_mock)
