from pathlib import Path

import pytest
from nodestream.pipeline import PipelineFile, PipelineInitializationArguments
from nodestream.pipeline.scope_config import ScopeConfig

import nodestream_github

_PIPELINE_DIR = Path(nodestream_github.__file__).parent
_PIPELINE_FILES = sorted(_PIPELINE_DIR.glob("github_*.yaml"))
_TEST_CONFIG = {
    "auth_token": "test-token",
    "collecting": False,
    "github_hostname": "github.example.com",
    "user_agent": "test-agent",
}


def test_all_bundled_pipelines_discovered():
    assert [pipeline.name for pipeline in _PIPELINE_FILES] == [
        "github_audit.yaml",
        "github_organizations.yaml",
        "github_repos.yaml",
        "github_teams.yaml",
        "github_users.yaml",
    ]


@pytest.mark.parametrize("pipeline_file", _PIPELINE_FILES, ids=lambda path: path.name)
def test_bundled_pipeline_initializes(pipeline_file: Path):
    """Every bundled pipeline constructs under the installed nodestream.

    Guards the extractor/interpretation argument surface the YAMLs rely on;
    pipeline construction is where the nodestream 0.16 positional-shift
    regression originally surfaced.
    """
    pipeline = PipelineFile(pipeline_file).load_pipeline(
        PipelineInitializationArguments(
            effective_config_values=ScopeConfig(_TEST_CONFIG)
        )
    )
    assert len(pipeline.steps) >= 2
