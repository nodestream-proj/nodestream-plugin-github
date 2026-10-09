# nodestream-plugin-github

# Overview

This plugin provides a way to scrape GitHub data from the REST api and ingest
them as extractors in nodestream pipelines.

# Setup Neo4j

1. Download and install Neo4j: https://neo4j.com/docs/desktop-manual/current/installation/download-installation/
2. Create and start database (version 5.7.0: https://neo4j.com/docs/desktop-manual/current/operations/create-dbms/
3. Install APOC: https://neo4j.com/docs/apoc/5/installation/

# Create GitHub credentials

1. Create and GitHub access
   codes: https://docs.github.com/en/enterprise-server@3.12/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
   NOTE: These values will be used in your `.env`

# Install and run the app

1. Install python3: https://www.python.org/downloads/
2. Install poetry: https://python-poetry.org/docs/#installation
3. Install nodestream: https://nodestream-proj.github.io/nodestream/0.5/docs/tutorial/
4. Generate a new nodestream project
5. Add `nodestream-github` to your project dependencies in your nodestream projects pyproject.toml file.
6. Install necessary dependencies: `poetry install`
7. In `nodestream.yaml` add the following:

```yaml
plugins:
  - name: github
    config:
      github_hostname: github.example.com
      auth_token: !env GITHUB_ACCESS_TOKEN
      user_agent: skip-jbristow-test
      per_page: 100
      collecting:
        all_public: True
      rate_limit_per_minute: 225
    targets:
      - my-db:
    pipelines:
      - name: github_repos
      - name: github_teams
targets:
  database: neo4j
  uri: bolt://localhost:7687
  username: neo4j
  password: neo4j123
```

1. Set environment variables in your terminal session for: `GITHUB_ACCESS_TOKEN`.
2. Verify nodestream has loaded the pipelines: `poetry run nodestream show`
3. Use nodestream to run the pipelines: `poetry run nodestream run <pipeline-name> --target my-db`

# Rate limiting

The client keeps its request rate at or below 90% of the limit that the server advertises for your token. It reads the `x-ratelimit-*` headers on each response. It slows down when the remaining budget would run out before the reset. The pace never drops below one request per minute. A `rate_limit_per_minute` that you set stays an upper bound.

The client meters the pace in whole-second windows, so it does not send a whole minute of requests at once. A pace of 75 requests per minute is 5 requests per 4 seconds. A slow pace uses a longer window. A request that finds the window full waits and retries.

If a request is still rate limited, the client waits for the reset time or the `retry-after` time that the server states. It then retries. When the server states no time, the client waits at least one minute. A permission failure is not retried.

The setting `max_retry_wait_seconds` caps only the exponential backoff. It does not cap the wait for a server rate limit. If retries run out, the client logs a warning and skips that data. The run continues.

A GitHub Enterprise Server instance leaves rate limits off by default. Such a server sends no limit headers, so the client keeps its fixed pace. The default is 216 requests per minute, or 7 requests per 2 seconds.

# Using make

1. Install make (ie. `brew install make`)
2. Run `make run`

# Contributing

When contributing, make sure to sign your commits. To find out more about how to do this, refer to
this [GitHub documentation](https://docs.github.com/en/authentication/managing-commit-signature-verification/signing-commits).

# Authors

* Jon Bristow
* Zach Probst
* Rohith Reddy
