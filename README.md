# nodestream-plugin-github

# Overview
This plugin provides a way to scrape github data from the REST api and ingest
them as extractors in nodestream pipelines.


# Setup Neo4j
1. Download and install Neo4j: https://neo4j.com/docs/desktop-manual/current/installation/download-installation/
1. Create and start database (version 5.7.0: https://neo4j.com/docs/desktop-manual/current/operations/create-dbms/
1. Install APOC: https://neo4j.com/docs/apoc/5/installation/

# Create github credentials 
1. Create and github access codes: https://docs.github.com/en/enterprise-server@3.12/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
NOTE: These values will be used in your `.env` 

# Install and run the app
1. Install python3: https://www.python.org/downloads/ 
1. Install poetry: https://python-poetry.org/docs/#installation 
1. Install nodestream: https://nodestream-proj.github.io/nodestream/0.5/docs/tutorial/
1. Generate a new nodestream project
1. Add `nodestream-github` to your project dependencies in your nodestream projects pyproject.toml file.
1. Install necessary dependencies: `poetry install`
1. In `nodestream.yaml` add the following:
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
1. Verify nodestream has loaded the pipelines: `poetry run nodestream show`
1. Use nodestream to run the pipelines: `poetry run nodestream run <pipeline-name> --target my-db`

# Using make
1. Install make (ie. `brew install make`)
1. Run `make run`


# Authors
* Jon Bristow
* Zach Probst
