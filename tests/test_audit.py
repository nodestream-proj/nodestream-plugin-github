import pytest

from nodestream_github import GithubAuditLogExtractor
from tests.data.audit import GITHUB_AUDIT
from tests.mocks.githubrest import (
    DEFAULT_HOSTNAME,
    DEFAULT_PER_PAGE,
    GithubHttpxMock,
)


@pytest.fixture
def audit_client() -> GithubAuditLogExtractor:
    return GithubAuditLogExtractor(
        auth_token="test-token",
        github_hostname=DEFAULT_HOSTNAME,
        user_agent="test-agent",
        max_retries=0,
        per_page=DEFAULT_PER_PAGE,
        enterprise_name="test-enterprise",
        actions=["protected_branch.create"],
    )


@pytest.mark.asyncio
async def test_get_audit(
    audit_client: GithubAuditLogExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.get_enterprise_audit_logs(status_code=200, json=GITHUB_AUDIT)

    all_records = [record async for record in audit_client.extract_records()]
    assert all_records == GITHUB_AUDIT
