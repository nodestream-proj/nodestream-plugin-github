from nodestream_github.types import Webhook


def webhook(
    *,
    webhook_type: str = "Repository",
    owner_login: str = "octocat",
    repo_name: str = "Hello-World",
    webhook_id: int = 12345678,
) -> Webhook:
    return {
        "type": webhook_type,
        "id": 12345678,
        "name": "web",
        "active": True,
        "events": ["push", "pull_request"],
        "config": {
            "content_type": "json",
            "insecure_ssl": "0",
            "url": "https://example.com/webhook",
        },
        "updated_at": "2019-06-03T00:57:16Z",
        "created_at": "2019-06-03T00:57:16Z",
        "url": f"https://HOSTNAME/repos/{owner_login}/{repo_name}/hooks/{webhook_id}",
        "test_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/hooks/{webhook_id}/test"
        ),
        "ping_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/hooks/{webhook_id}/pings"
        ),
        "deliveries_url": (
            f"https://HOSTNAME/repos/{owner_login}/{repo_name}/hooks/{webhook_id}/deliveries"
        ),
        "last_response": {"code": None, "status": "unused", "message": None},
    }


HELLO_WORLD_WEBHOOK = webhook()
