import pytest
from freezegun import freeze_time

from nodestream_github import GithubAuditLogExtractor
from nodestream_github.audit import generate_date_range, validate_lookback_period
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
    ("lookback_period", "expected_path", "expected_dates"),
    [
        (
            {"days": 7},
            "action:protected_branch.create created:2025-07-25",
            ["2025-07-25", "2025-07-26", "2025-07-27", "2025-07-28", "2025-07-29", "2025-07-30", "2025-07-31", "2025-08-01"],
        ),
        (
            {"months": 2},
            "action:protected_branch.create created:2025-06-01",
            ["2025-06-01", "2025-06-02", "2025-06-03"],
        ),
        (
            {"years": 1},
            "action:protected_branch.create created:2024-08-01",
            ["2024-08-01", "2024-08-02", "2024-08-03"],
        ),
        (
            {"days": 15, "months": 1},
            "action:protected_branch.create created:2025-06-16",
            ["2025-06-16", "2025-06-17", "2025-06-18"],
        ),
        (
            {"days": 10, "months": 1, "years": 1},
            "action:protected_branch.create created:2024-06-21",
            ["2024-06-21", "2024-06-22", "2024-06-23"],
        ),
    ],
)
@pytest.mark.asyncio
async def test_get_audit_lookback_periods(
    gh_rest_mock: GithubHttpxMock,
    lookback_period: dict[str, int] | None,
    expected_path: str,
    expected_dates: list[str],
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

    if len(expected_dates) > 1:
        for date in expected_dates[1:]:
            search_phrase = f"action:protected_branch.create created:{date}"
            gh_rest_mock.get_enterprise_audit_logs(
                status_code=200,
                search_phrase=search_phrase,
                json=GITHUB_AUDIT,
            )

    # replacing generate_date_range with test dates
    # so that we don't iterate through all dates
    import nodestream_github.audit as client_module

    original_generate = client_module.generate_date_range
    client_module.generate_date_range = lambda x: expected_dates

    try:
        all_records = [record async for record in extractor.extract_records()]
        expected_output = GITHUB_EXPECTED_OUTPUT * len(expected_dates)
        assert all_records == expected_output
    finally:
        client_module.generate_date_range = original_generate


# Test generate_date_range


@pytest.mark.parametrize(
    ("lookback_period", "expected_length", "expected_first", "expected_last"),
    [
        (
            {},
            0,
            None,
            None,
        ),
        (
            {"days": 3},
            4,
            "2025-07-29",
            "2025-08-01",
        ),
        (
            {"days": 0},
            1,
            "2025-08-01",
            "2025-08-01",
        ),
        (
            {"months": 1},
            32,
            "2025-07-01",
            "2025-08-01",
        ),
        (
            {"years": 1},
            366,
            "2024-08-01",
            "2025-08-01",
        ),
        (
            {"months": 1, "days": 5},
            37,
            "2025-06-26",
            "2025-08-01",
        ),
        (
            {"years": 1, "months": 2, "days": 10},
            437,
            "2024-05-22",
            "2025-08-01",
        ),
    ],
)
@freeze_time("2025-08-01")
def test_generate_date_range_parameterized(
    lookback_period: dict[str, int],
    expected_length: int,
    expected_first: str | None,
    expected_last: str | None,
):
    result = generate_date_range(lookback_period)

    assert len(result) == expected_length
    if expected_length > 0:
        assert result[0] == expected_first
        assert result[-1] == expected_last


# Test validate_lookback_period


@pytest.mark.parametrize(
    ("input_period", "expected_result"),
    [
        (
            {"days": 7, "months": 2, "years": 1},
            {"days": 7, "months": 2, "years": 1},
        ),
        (
            {},
            {},
        ),
        (
            {"days": 30},
            {"days": 30},
        ),
        (
            {"days": "7", "months": "2"},
            {"days": 7, "months": 2},
        ),
    ],
)
def test_validate_lookback_period_valid_cases(
    input_period: dict[str, int | str],
    expected_result: dict[str, int],
):
    result = validate_lookback_period(input_period)
    assert result == expected_result


@pytest.mark.parametrize(
    ("input_period",),
    [
        ({"days": 0},),
        ({"days": -5},),
        ({"days": 7, "months": -1, "years": 2},),
        ({"days": "0"},),
        ({"months": "-10"},),
        ({"days": "invalid"},),
        ({"days": []},),
        ({"days": None},),
    ],
)
def test_validate_lookback_period_invalid_cases(
    input_period: dict[str, int | str | list | None],
):
    with pytest.raises(ValueError, match="Formatting lookback period failed"):
        validate_lookback_period(input_period)
