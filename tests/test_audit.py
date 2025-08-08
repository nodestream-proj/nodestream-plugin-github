import pytest
from freezegun import freeze_time

from nodestream_github import GithubAuditLogExtractor
from tests.data.audit import GITHUB_AUDIT, GITHUB_EXPECTED_OUTPUT
from tests.mocks.githubrest import (
    DEFAULT_HOSTNAME,
    DEFAULT_PER_PAGE,
    GithubHttpxMock,
)


@pytest.mark.parametrize(
    ("actions", "actors", "exclude_actors", "lookback_period", "expected_path"),
    [
        # Basic single action
        (
            ["protected_branch.create"],
            None,
            None,
            None,
            "action:protected_branch.create",
        ),
        # Multiple actions
        (
            ["protected_branch.create", "repo.download_zip", "team.add_member"],
            None,
            None,
            None,
            (
                "action:protected_branch.create action:repo.download_zip "
                "action:team.add_member"
            ),
        ),
        # Single actor
        (None, ["octocat"], None, None, "actor:octocat"),
        # Multiple actors
        (None, ["octocat", "monalisa"], None, None, "actor:octocat actor:monalisa"),
        # Single exclude actor
        (None, None, ["exclude-user"], None, "-actor:exclude-user"),
        # Multiple exclude actors
        (
            None,
            None,
            ["exclude-user1", "exclude-user2"],
            None,
            "-actor:exclude-user1 -actor:exclude-user2",
        ),
        # Actions + actors
        (
            ["org.create", "repo.destroy"],
            ["octocat"],
            None,
            None,
            "action:org.create action:repo.destroy actor:octocat",
        ),
        # Actions + exclude_actors
        (
            ["team.add_member"],
            None,
            ["bot-user"],
            None,
            "action:team.add_member -actor:bot-user",
        ),
        # Actors + exclude_actors
        (
            None,
            ["octocat", "monalisa"],
            ["bot-user"],
            None,
            "actor:octocat actor:monalisa -actor:bot-user",
        ),
        # All parameters combined
        (
            ["protected_branch.create", "repo.download_zip"],
            ["octocat"],
            ["exclude-user"],
            None,
            (
                "action:protected_branch.create action:repo.download_zip "
                "actor:octocat -actor:exclude-user"
            ),
        ),
        # Maximum complexity
        (
            ["org.create", "team.add_member", "repo.destroy"],
            ["octocat", "monalisa", "admin-user"],
            ["bot-user1", "bot-user2", "exclude-admin"],
            None,
            (
                "action:org.create action:team.add_member action:repo.destroy "
                "actor:octocat actor:monalisa actor:admin-user "
                "-actor:bot-user1 -actor:bot-user2 -actor:exclude-admin"
            ),
        ),
        # All None values
        (None, None, None, None, ""),
        # Empty lists
        ([], [], [], None, ""),
    ],
)
@pytest.mark.asyncio
async def test_get_audit_parameterized(
    gh_rest_mock: GithubHttpxMock,
    actions: list[str] | None,
    actors: list[str] | None,
    exclude_actors: list[str] | None,
    lookback_period: dict[str, int] | None,
    expected_path: str,
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

    gh_rest_mock.get_enterprise_audit_logs(
        status_code=200,
        search_phrase=expected_path,
        json=GITHUB_AUDIT,
    )

    all_records = [record async for record in extractor.extract_records()]
    assert all_records == GITHUB_EXPECTED_OUTPUT


@freeze_time("2025-08-01")
@pytest.mark.parametrize(
    ("lookback_period", "expected_path"),
    [
        (
            {"days": 7},
            "action:protected_branch.create created:>=2025-07-25",
        ),
        (
            {"months": 2},
            "action:protected_branch.create created:>=2025-06-01",
        ),
        (
            {"years": 1},
            "action:protected_branch.create created:>=2024-08-01",
        ),
        (
            {"days": 15, "months": 1},
            "action:protected_branch.create created:>=2025-06-16",
        ),
        (
            {"days": 10, "months": 1, "years": 1},
            "action:protected_branch.create created:>=2024-06-21",
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_audit_lookback_periods(
    gh_rest_mock: GithubHttpxMock,
    lookback_period: dict[str, int] | None,
    expected_path: str,
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

    gh_rest_mock.get_enterprise_audit_logs(
        status_code=200,
        search_phrase=expected_path,
        json=GITHUB_AUDIT,
    )

    all_records = [record async for record in extractor.extract_records()]
    assert all_records == GITHUB_EXPECTED_OUTPUT
