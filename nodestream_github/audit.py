"""
Nodestream Extractor that extracts audit logs from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator
from typing import Any

from nodestream.pipeline import Extractor

from .client import GithubRestApiClient
from .logging import get_plugin_logger
from .types import GithubAuditLog

logger = get_plugin_logger(__name__)


class GithubAuditLogExtractor(Extractor):
    """
    Extracts audit logs from the GitHub REST API.
    You can pass the enterprise_name, actions and lookback_period to the extractor
    along with the regular GitHub parameters.

    lookback_period can contain keys for days, months, and/or years as ints
    actions can be found in the GitHub documentation
    https://docs.github.com/en/enterprise-server@3.12/admin/monitoring-activity-in-your-enterprise/reviewing-audit-logs-for-your-enterprise/searching-the-audit-log-for-your-enterprise#search-based-on-the-action-performed
    """

    def __init__(
        self,
        enterprise_name: str,
        actions: list[str] | None = None,
        lookback_period: dict[str, int] | None = None,
        **github_client_kwargs: Any | None,
    ):
        self.enterprise_name = enterprise_name
        self.client = GithubRestApiClient(**github_client_kwargs)
        self.lookback_period = lookback_period
        self.actions = actions

    async def extract_records(self) -> AsyncGenerator[GithubAuditLog]:
        async for audit in self.client.fetch_enterprise_audit_log(
            self.enterprise_name, self.actions, self.lookback_period
        ):
            audit["timestamp"] = audit.pop("@timestamp")
            yield audit
