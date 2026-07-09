---
title: "fix: Forward relationship interpretation args by keyword for nodestream 0.16"
type: fix
status: active
date: 2026-07-09
---

# fix: Forward relationship interpretation args by keyword for nodestream 0.16

## Summary

Fix the nodestream 0.16 incompatibility in the plugin's two custom relationship interpretation aliases by forwarding arguments to the base class by keyword instead of position, and expose nodestream 0.16's new `relationship_creation_rule` option through both aliases.

## Problem Frame

nodestream 0.16.0 inserted a new `relationship_creation_rule` parameter into `RelationshipInterpretation.__init__`, between `node_creation_rule` and `key_normalization`. Both `UserRelationshipInterpretation` (`nodestream_github/interpretations/relationship/user.py`) and `RepositoryRelationshipInterpretation` (`nodestream_github/interpretations/relationship/repository.py`) call `super().__init__` with a fully positional argument list in the pre-0.16 order. Under nodestream ≥0.16 the `key_normalization` dict lands in the `relationship_creation_rule` slot, and the base class's enum coercion raises `ValueError: {'do_lowercase_strings': False} is not a valid RelationshipCreationRule`. Every bundled pipeline that passes `key_normalization` through these aliases (teams, repos, organizations, users) fails at construction; the remaining shifted parameters (`properties_normalization`, `node_additional_types`) would silently land on the wrong attributes even when no error is raised.

The repo's tests did not catch this for two reasons: the existing interpretation tests construct with only a relationship type (all shifted parameters default to `None`), and the local venv holds nodestream 0.14.17 while `poetry.lock` pins 0.16.0, so the suite exercises the wrong version.

## Requirements

- R1. Constructing `github-user-relationship` and `github-repo-relationship` interpretations with `key_normalization` (and the other optional arguments) succeeds under nodestream 0.16, with every argument landing on its intended base-class attribute.
- R2. The aliases forward arguments to `RelationshipInterpretation` by name, so future parameter insertions in nodestream cannot silently shift argument meaning again.
- R3. YAML authors can set `relationship_creation_rule` through both aliases; omitting it preserves nodestream's default behavior (`EAGER`).
- R4. The test suite runs against the locked nodestream version (0.16.0), not a stale venv.

## Key Technical Decisions

- **Keyword forwarding, not reordered positional args**: matching 0.16's positional order would fix today's error but recreate the same failure mode on the next upstream signature change. Named arguments are the root-cause fix.
- **`relationship_creation_rule` passed through as an optional value defaulting to `None`**: the base class owns the default (`EAGER`); re-declaring defaults in the subclasses would create a second source of truth that can drift.
- **No version bump in this change**: this repo cuts releases through separate release PRs (see `Release 0.16.0`, `Release 0.15.0` in history); versioning stays in that flow.

## Implementation Units

### U1. Fix positional argument shift in both relationship aliases

- **Goal**: Both custom interpretations construct correctly under nodestream 0.16, with all optional arguments mapped to the right base-class parameters.
- **Requirements**: R1, R2, R4
- **Dependencies**: none
- **Files**: `nodestream_github/interpretations/relationship/user.py`, `nodestream_github/interpretations/relationship/repository.py`, `tests/interpretations/relationship/test_user.py`, `tests/interpretations/relationship/test_repository.py`
- **Approach**: Sync the venv to the lockfile first so tests exercise nodestream 0.16.0 (R4) — without this, the regression tests pass vacuously against 0.14.17. Then convert each `super().__init__` call from the positional list to keyword arguments, leaving the subclass signatures and baked-in node type / key / properties values unchanged.
- **Execution note**: Test-first — write the `key_normalization` construction test, confirm it fails with the `RelationshipCreationRule` `ValueError` under 0.16.0, then apply the keyword conversion.
- **Patterns to follow**: existing test shape in `tests/interpretations/relationship/test_user.py` (`ProviderContext` fixture, direct attribute assertions).
- **Test scenarios**:
  - Constructing each alias with `key_normalization={"do_lowercase_strings": False}` succeeds and the instance's `key_normalization` reflects that value (this is the teams-pipeline failure case).
  - Constructing each alias with `properties_normalization` and `node_additional_types` set lands each value on its matching attribute — guards the silent one-slot shift, not just the crashing one.
  - Existing default-construction tests (relationship type only) still pass unchanged.
- **Verification**: New construction tests fail before the code change and pass after; full suite, formatters, and linters clean against nodestream 0.16.0.

### U2. Expose `relationship_creation_rule` through both aliases

- **Goal**: YAML pipeline authors can set nodestream 0.16's `relationship_creation_rule` on `github-user-relationship` and `github-repo-relationship`.
- **Requirements**: R3
- **Dependencies**: U1
- **Files**: `nodestream_github/interpretations/relationship/user.py`, `nodestream_github/interpretations/relationship/repository.py`, `tests/interpretations/relationship/test_user.py`, `tests/interpretations/relationship/test_repository.py`
- **Approach**: Add an optional `relationship_creation_rule` parameter to each subclass signature and forward it by keyword. nodestream's declarative loader passes YAML `arguments` as keyword arguments, so no YAML or loader changes are needed.
- **Test scenarios**:
  - Constructing with `relationship_creation_rule="CREATE"` yields an instance whose rule is `CREATE`.
  - Omitting the argument preserves the base default (`EAGER`).
  - An invalid value (e.g., `"BOGUS"`) raises the enum coercion `ValueError` from nodestream — confirming errors surface at construction, not ingest time.
- **Verification**: New option tests pass; full suite, formatters, and linters clean.

## Scope Boundaries

- No changes to the bundled pipeline YAMLs — the bug is in the Python argument forwarding, not the YAML.
- No changes to nodestream core; its 0.16 signature is correct and this plugin adapts to it.

### Deferred to Follow-Up Work

- Exposing nodestream 0.16's `node_update_last_ingested` / `relationship_update_last_ingested` parameters through the aliases — same passthrough pattern, add when a pipeline needs them.
- Patch release / version bump — handled by this repo's separate release-PR flow.

## Sources & Research

- Root cause reproduced in-session against the nodestream 0.16.0 wheel: constructing `UserRelationshipInterpretation` with `key_normalization` raises the exact reported error; the installed 0.14.17 signature has no `relationship_creation_rule` parameter, the 0.16.0 signature does (`nodestream/interpreting/interpretations/relationship_interpretation.py`).
- Affected argument-forwarding sites: `nodestream_github/interpretations/relationship/user.py` and `nodestream_github/interpretations/relationship/repository.py` (the only two subclasses of `RelationshipInterpretation` in the repo).
- Pipelines exercising the aliases with `key_normalization`: `nodestream_github/github_teams.yaml`, `github_repos.yaml`, `github_organizations.yaml`, `github_users.yaml`.
