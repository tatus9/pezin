# hook-installation Specification

## Purpose
TBD - created by archiving change harden-hooks-and-changelog. Update Purpose after archive.
## Requirements
### Requirement: Generated hooks run under the installing interpreter

`pezin install-hooks` SHALL write hook scripts whose shebang references the
absolute path of the interpreter executing the install command, so that the
hooks import pezin from the same environment (pipx, uv tool, virtualenv) that
provided the CLI.

#### Scenario: hooks work without the venv on PATH

- **WHEN** `pezin install-hooks` runs from a virtualenv whose `bin` directory is not on `PATH`, and the user makes a `feat:` commit
- **THEN** the hook executes successfully and the version bump, changelog update, amend, and tag all complete

#### Scenario: shebang is pinned

- **WHEN** a hook script is generated
- **THEN** its first line is the absolute path of `sys.executable` of the installing process, not `/usr/bin/env python3`

### Requirement: Missing pezin installation never blocks a commit

When a generated hook cannot import pezin, it SHALL print a warning to stderr
advising the user to re-run `pezin install-hooks` from the correct environment
and SHALL exit with status 0, so commits are never aborted by a missing
installation.

#### Scenario: import failure degrades gracefully

- **WHEN** a generated hook runs on a machine where its pinned interpreter can no longer import pezin
- **THEN** the commit proceeds, and a warning mentioning `pezin install-hooks` appears on stderr
