"""
Nodestream Extractor that extracts audit logs from the GitHub REST API.

Developed using Enterprise Server 3.12
https://docs.github.com/en/enterprise-server@3.12/rest?apiVersion=2022-11-28
"""

from collections.abc import AsyncGenerator
from typing import List

from nodestream.pipeline import Extractor

from .client import GithubRestApiClient
from .logging import get_plugin_logger
from .types import GithubAuditLog

logger = get_plugin_logger(__name__)


class GithubAuditLogExtractor(Extractor):
    def __init__(
        self, enterprise_name: str, events: List[str], **github_client_kwargs: any
    ):
        self.enterprise_name = enterprise_name
        self.client = GithubRestApiClient(**github_client_kwargs)
        self.events = events

    async def extract_records(self) -> AsyncGenerator[GithubAuditLog]:
        async for audit in self.client.fetch_enterprise_audit_log(
            self.enterprise_name, self.events
        ):
            yield audit
