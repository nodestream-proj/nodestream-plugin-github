import pytest

from nodestream_github import GithubAuditLogExtractor
from tests.data.audit import GITHUB_AUDIT, GITHUB_EXPECTED_OUTPUT
from tests.mocks.githubrest import (
    DEFAULT_HOSTNAME,
    DEFAULT_PER_PAGE,
    GithubHttpxMock,
)


@pytest.fixture
def audit_extractor() -> GithubAuditLogExtractor:
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
    audit_extractor: GithubAuditLogExtractor, gh_rest_mock: GithubHttpxMock
):
    gh_rest_mock.get_enterprise_audit_logs(status_code=200, json=GITHUB_AUDIT)

    all_records = [record async for record in audit_extractor.extract_records()]
    assert all_records == GITHUB_EXPECTED_OUTPUT
