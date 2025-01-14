from collections.abc import AsyncGenerator

import httpx
import pytest

from nodestream_github import GithubUserExtractor
from tests.data.repos import HELLO_WORLD_REPO
from tests.data.users import OCTOCAT_USER
from tests.mocks.githubrest import DEFAULT_HOSTNAME, GithubHttpxMock


@pytest.fixture
def user_client() -> GithubUserExtractor:
    return GithubUserExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
    )


async def to_list(async_generator: AsyncGenerator) -> list:
    output = []
    async for item in async_generator:
        output.append(item)
    return output


@pytest.mark.asyncio
async def test_github_user_extractor(
    user_client: GithubUserExtractor, gh_rest_mock: GithubHttpxMock
):

    gh_rest_mock.all_users(json=[OCTOCAT_USER])
    gh_rest_mock.get_repos_for_user("octocat", "all", json=[HELLO_WORLD_REPO])

    actual = [record async for record in user_client.extract_records()]

    assert actual == [
        OCTOCAT_USER
        | {
            "repositories": [{
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
async def test_github_user_extractor_repo_fail(
    user_client: GithubUserExtractor,
    gh_rest_mock: GithubHttpxMock,
):

    gh_rest_mock.all_users(json=[OCTOCAT_USER])
    gh_rest_mock.get_repos_for_user(
        "octocat", "all", status_code=httpx.codes.SERVICE_UNAVAILABLE
    )
    actual = [user async for user in user_client.extract_records()]

    assert actual == [OCTOCAT_USER | {"repositories": []}]
