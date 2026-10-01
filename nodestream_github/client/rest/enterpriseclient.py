from collections.abc import AsyncGenerator
from typing import Any

import httpx

from nodestream_github.client.rest.githubclient import (
    GithubRestApiClient,
    log_fetch_problem,
)


class EnterpriseClient:
    def __init__(self, client: GithubRestApiClient):
        self.client: GithubRestApiClient = client

    async def fetch_enterprise_audit_log(
        self,
        enterprise_name: str,
        search_phrase: str | None = None,
    ) -> AsyncGenerator[dict[str, Any]]:
        """Fetches enterprise-wide audit log data
        https://docs.github.com/en/enterprise-server@3.14/rest/enterprise-admin/audit-log?apiVersion=2022-11-28#get-the-audit-log-for-an-enterprise
        """
        try:
            params = {"phrase": search_phrase} if search_phrase else {}
            async for audit in self.client.get_paginated(
                f"enterprises/{enterprise_name}/audit-log", params=params
            ):
                yield audit
        except httpx.HTTPError as e:
            log_fetch_problem("audit log", e)
