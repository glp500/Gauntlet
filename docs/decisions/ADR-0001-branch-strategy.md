# ADR-0001: Early Prototype Branch Strategy

- Status: Accepted
- Date: 2026-04-25

## Context

Gauntlet is being built inside a repository that already contains upstream snapshots
and local exploratory work. Early development needs a stable integration branch that
is separate from `main`, while still allowing short-lived feature branches for
focused work.

## Decision

All early local development must start from `early-prototype`.

Required branch behavior:

- check the active branch before editing with `git branch --show-current`
- if the active branch is not `early-prototype`, switch to it or create it first
- do not push directly to `main`
- do not use an unqualified `git push` unless the upstream is confirmed to be
  `origin/early-prototype`
- when pushing early prototype work, use `git push -u origin early-prototype`

Feature branches are allowed, but they must branch from `early-prototype` and target
`early-prototype` in pull requests during the early repository phase.

Recommended naming:

- `feature/<area>-<slug>`
- `spike/<area>-<question>`
- `integration/<milestone>`

## Rationale

`main` should remain protected and reviewable while the repository contract is still
being established. A shared early integration branch reduces accidental pushes to
`main` and keeps the first milestones aligned around one branch target.

Long-lived collaborator branches and permanent subsystem branches are explicitly
avoided because they create drift, unclear ownership, and expensive reintegration
work.

## Consequences

- early prototype pull requests target `early-prototype`, not `main`
- branch instructions must stay consistent across `program.md` and repo ADRs
- contributors need to preserve local uncommitted work when moving from `main` to
  `early-prototype`

