import pytest

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
        target_date=None,
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
    [{"days": 7}, {"months": 2}, {"days": 15, "months": 1}],
)
@pytest.mark.asyncio
async def test_get_audit_lookback_periods(
    gh_rest_mock: GithubHttpxMock,
    lookback_period: dict[str, int] | None,
):
    from nodestream_github.client.githubclient import generate_date_range

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

    # Generate the expected dates that will be queried
    dates = generate_date_range(lookback_period)

    # Mock each individual date request
    for date in dates:
        expected_search_phrase = f"action:protected_branch.create created:{date}"
        gh_rest_mock.get_enterprise_audit_logs(
            status_code=200,
            search_phrase=expected_search_phrase,
            json=GITHUB_AUDIT,
        )

    all_records = [record async for record in extractor.extract_records()]
    # Since we're making multiple calls with the same data, we expect multiple copies
    expected_output = GITHUB_EXPECTED_OUTPUT * len(dates)
    assert all_records == expected_output
