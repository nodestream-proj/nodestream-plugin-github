from typing import AsyncGenerator

import pytest
from pytest_httpx import HTTPXMock

from nodestream_github import GithubUserExtractor
from tests.data.repos import HELLO_WORLD_REPO
from tests.data.users import OCTOCAT_USER


@pytest.fixture
def user_client():
    return GithubUserExtractor(
        auth_token="test-token",
        github_endpoint="https://test-example.githhub.intuit.com",
        user_agent="test-agent",
        max_retries=0,
    )


async def to_list(async_generator: AsyncGenerator) -> list:
    output = []
    async for item in async_generator:
        output.append(item)
    return output


@pytest.mark.asyncio
async def test_github_user_extractor(user_client, httpx_mock: HTTPXMock):

    httpx_mock.add_response(
        status_code=200,
        url="https://test-example.githhub.intuit.com/users?per_page=100",
        json=[OCTOCAT_USER],
    )
    httpx_mock.add_response(
        status_code=200,
        url="https://test-example.githhub.intuit.com/users/octocat/repos?per_page=100&type=all",
        json=[HELLO_WORLD_REPO],
    )

    actual = await to_list(user_client.extract_records())

    assert actual == [
        OCTOCAT_USER
        | {
            "repos": [{
                "full_name": "octocat/Hello-World",
                "id": 1296269,
                "name": "Hello-World",
                "node_id": "MDEwOlJlcG9zaXRvcnkxMjk2MjY5",
                "permissions": {"admin": False, "pull": True, "push": False},
                "url": "https://HOSTNAME/repos/octocat/Hello-World",
            }]
        }
    ]


@pytest.mark.asyncio
async def test_github_user_extractor_repo_fail(user_client, httpx_mock: HTTPXMock):

    httpx_mock.add_response(
        status_code=200,
        url="https://test-example.githhub.intuit.com/users?per_page=100",
        json=[OCTOCAT_USER],
    )
    httpx_mock.add_response(
        status_code=503,
        url="https://test-example.githhub.intuit.com/users/octocat/repos?per_page=100&type=all",
    )
    actual = await to_list(user_client.extract_records())

    assert actual == [OCTOCAT_USER]
