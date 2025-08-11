"""
Nodestream Extractor that extracts audit logs from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

from dateutil.relativedelta import relativedelta
from nodestream.pipeline import Extractor

from .client import GithubRestApiClient
from .logging import get_plugin_logger
from .types import GithubAuditLog

logger = get_plugin_logger(__name__)


def generate_date_range(lookback_period: dict[str, int]) -> list[str]:
    """
    Generate a list of date strings in YYYY-MM-DD format for
    the given lookback period.
    """
    if not lookback_period:
        return []

    end_date = datetime.now(tz=UTC).date()
    start_date = (datetime.now(tz=UTC) - relativedelta(**lookback_period)).date()

    delta_days = (end_date - start_date).days + 1
    return [
        (start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(delta_days)
    ]


def build_search_phrase(
    actions: list[str],
    actors: list[str],
    exclude_actors: list[str],
    target_date: str | None = None,
) -> str:
    # adding action-based filtering
    actions_phrase = ""
    if actions:
        actions_phrase = " ".join(f"action:{action}" for action in actions)

    # adding date-based filtering for a specific date
    date_filter = f"created:{target_date}" if target_date else ""

    # adding actor-based filtering
    actors_phrase = ""
    if actors:
        actors_phrase = " ".join(f"actor:{actor}" for actor in actors)

    # adding exclude_actors based filtering
    exclude_actors_phrase = ""
    if exclude_actors:
        exclude_actors_phrase = " ".join(f"-actor:{actor}" for actor in exclude_actors)
    return " ".join(
        section
        for section in [
            actions_phrase,
            date_filter,
            actors_phrase,
            exclude_actors_phrase,
        ]
        if section
    ).strip()


def validate_lookback_period(lookback_period: dict[str, int]) -> dict[str, int]:
    """Sanitize the lookback period to only include valid keys."""

    def validate_positive_int(value: int) -> int:
        converted = int(value)
        if converted <= 0:
            negative_value_exception_msg = (
                f"Lookback period values must be positive: {value}"
            )
            raise ValueError(negative_value_exception_msg)
        return converted

    try:
        return {k: validate_positive_int(v) for k, v in lookback_period.items()}
    except Exception as e:
        exception_msg = "Formatting lookback period failed"
        raise ValueError(exception_msg) from e


class GithubAuditLogExtractor(Extractor):
    """
    Extracts audit logs from the GitHub REST API.
    You can pass the enterprise_name, actions, actors, exclude_actors
    and lookback_period to the extractor along with the regular
    GitHub parameters.

    lookback_period can contain keys for days, months, and/or years as ints
    actions, and actors/exclude_actors can be found in the GitHub documentation
    https://docs.github.com/en/enterprise-server@3.12/admin/monitoring-activity-in-your-enterprise/reviewing-audit-logs-for-your-enterprise/searching-the-audit-log-for-your-enterprise#search-based-on-the-action-performed
    """

    def __init__(
        self,
        enterprise_name: str,
        actions: list[str] | None = None,
        actors: list[str] | None = None,
        exclude_actors: list[str] | None = None,
        lookback_period: dict[str, int] | None = None,
        **github_client_kwargs: Any | None,
    ):
        self.enterprise_name = enterprise_name
        self.client = GithubRestApiClient(**github_client_kwargs)
        self.lookback_period = lookback_period
        self.actions = actions
        self.actors = actors
        self.exclude_actors = exclude_actors

    async def extract_records(self) -> AsyncGenerator[GithubAuditLog]:
        dates = generate_date_range(self.lookback_period) or [None]
        for target_date in dates:
            search_phrase = build_search_phrase(
                actions=self.actions,
                actors=self.actors,
                exclude_actors=self.exclude_actors,
                target_date=target_date,
            )
            async for audit in self.client.fetch_enterprise_audit_log(
                self.enterprise_name,
                search_phrase,
            ):
                audit["timestamp"] = audit.pop("@timestamp")
                yield audit
