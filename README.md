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
