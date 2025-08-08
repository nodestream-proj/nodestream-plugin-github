from datetime import UTC, datetime

import pytest
from dateutil.relativedelta import relativedelta

from nodestream_github import GithubAuditLogExtractor
from nodestream_github.client.githubclient import build_search_phrase
from tests.data.audit import GITHUB_AUDIT, GITHUB_EXPECTED_OUTPUT
from tests.mocks.githubrest import (
    DEFAULT_HOSTNAME,
    DEFAULT_PER_PAGE,
    GithubHttpxMock,
)


@pytest.mark.parametrize(
    ("actions", "actors", "exclude_actors", "lookback_period"),
    [
        # Basic single action
        (["protected_branch.create"], None, None, None),
        # Multiple actions
        (
            ["protected_branch.create", "repo.download_zip", "team.add_member"],
            None,
            None,
            None,
        ),
        # Single actor
        (None, ["octocat"], None, None),
        # Multiple actors
        (None, ["octocat", "monalisa"], None, None),
        # Single exclude actor
        (None, None, ["exclude-user"], None),
        # Multiple exclude actors
        (None, None, ["exclude-user1", "exclude-user2"], None),
        # Actions + actors
        (["org.create", "repo.destroy"], ["octocat"], None, None),
        # Actions + exclude_actors
        (["team.add_member"], None, ["bot-user"], None),
        # Actors + exclude_actors
        (None, ["octocat", "monalisa"], ["bot-user"], None),
        # All parameters combined
        (
            ["protected_branch.create", "repo.download_zip"],
            ["octocat"],
            ["exclude-user"],
            None,
        ),
        # Maximum complexity
        (
            ["org.create", "team.add_member", "repo.destroy"],
            ["octocat", "monalisa", "admin-user"],
            ["bot-user1", "bot-user2", "exclude-admin"],
            None,
        ),
        # All None values
        (None, None, None, None),
        # Empty lists
        ([], [], [], None),
    ],
)
@pytest.mark.asyncio
async def test_get_audit_parameterized(
    gh_rest_mock: GithubHttpxMock,
    actions: list[str] | None,
    actors: list[str] | None,
    exclude_actors: list[str] | None,
    lookback_period: dict[str, int] | None,
):
    extractor = GithubAuditLogExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        enterprise_name="test-enterprise",
        actions=actions,
        actors=actors,
        exclude_actors=exclude_actors,
        lookback_period=lookback_period,
    )

    expected_search_phrase = build_search_phrase(
        actions=actions or [],
        actors=actors or [],
        exclude_actors=exclude_actors or [],
        lookback_period={},
    )

    gh_rest_mock.get_enterprise_audit_logs(
        status_code=200,
        search_phrase=expected_search_phrase,
        json=GITHUB_AUDIT,
    )

    all_records = [record async for record in extractor.extract_records()]
    assert all_records == GITHUB_EXPECTED_OUTPUT


@pytest.mark.parametrize(
    "lookback_period",
    [
        {"days": 7},
        {"months": 2},
        {"years": 1},
        {"days": 15, "months": 1},
        {"days": 10, "months": 1, "years": 1},
    ],
)
@pytest.mark.asyncio
async def test_get_audit_lookback_periods(
    gh_rest_mock: GithubHttpxMock,
    lookback_period: dict[str, int] | None,
):
    extractor = GithubAuditLogExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        enterprise_name="test-enterprise",
        actions=["protected_branch.create"],
        lookback_period=lookback_period,
    )

    lookback_date = (datetime.now(tz=UTC) - relativedelta(**lookback_period)).strftime(
        "%Y-%m-%d"
    )
    expected_search_phrase = f"action:protected_branch.create created:>={lookback_date}"
    gh_rest_mock.get_enterprise_audit_logs(
        status_code=200,
        search_phrase=expected_search_phrase,
        json=GITHUB_AUDIT,
    )

    all_records = [record async for record in extractor.extract_records()]
    assert all_records == GITHUB_EXPECTED_OUTPUT
