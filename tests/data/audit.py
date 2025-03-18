from nodestream_github.types import GithubAuditLog


def audit() -> GithubAuditLog:
    return [
        {
            "@timestamp": 1606929874512,
            "action": "team.add_member",
            "actor": "octocat",
            "created_at": 1606929874512,
            "_document_id": "xJJFlFOhQ6b-5vaAFy9Rjw",
            "org": "octo-corp",
            "team": "octo-corp/example-team",
            "user": "monalisa",
        },
        {
            "@timestamp": 1606507117008,
            "action": "org.create",
            "actor": "octocat",
            "created_at": 1606507117008,
            "_document_id": "Vqvg6kZ4MYqwWRKFDzlMoQ",
            "org": "octocat-test-org",
        },
        {
            "@timestamp": 1605719148837,
            "action": "repo.destroy",
            "actor": "monalisa",
            "created_at": 1605719148837,
            "_document_id": "LwW2vpJZCDS-WUmo9Z-ifw",
            "org": "mona-org",
            "repo": "mona-org/mona-test-repo",
            "visibility": "private",
        },
    ]


def audit_expected_output() -> GithubAuditLog:
    return [
        {
            "timestamp": 1606929874512,
            "action": "team.add_member",
            "actor": "octocat",
            "created_at": 1606929874512,
            "_document_id": "xJJFlFOhQ6b-5vaAFy9Rjw",
            "org": "octo-corp",
            "team": "octo-corp/example-team",
            "user": "monalisa",
        },
        {
            "timestamp": 1606507117008,
            "action": "org.create",
            "actor": "octocat",
            "created_at": 1606507117008,
            "_document_id": "Vqvg6kZ4MYqwWRKFDzlMoQ",
            "org": "octocat-test-org",
        },
        {
            "timestamp": 1605719148837,
            "action": "repo.destroy",
            "actor": "monalisa",
            "created_at": 1605719148837,
            "_document_id": "LwW2vpJZCDS-WUmo9Z-ifw",
            "org": "mona-org",
            "repo": "mona-org/mona-test-repo",
            "visibility": "private",
        },
    ]

GITHUB_AUDIT = audit()
GITHUB_EXPECTED_OUTPUT = audit_expected_output()
