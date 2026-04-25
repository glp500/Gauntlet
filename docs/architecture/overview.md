# Gauntlet Architecture Overview

## Purpose

This document maps the top-level repository layout for the early Gauntlet prototype.
It exists to keep the first implementation slice focused on Gauntlet-owned interfaces
instead of broad edits across the upstream snapshots.

## Repository map

- `program.md` is the main product and architecture specification for the project.
- `gauntlet-sandbox/` is the first stable MVP target. It will hold the pipeline
  contract, project manifest, generated artifacts, and the six Python workflow
  modules used by early sandbox runs.
- `input/` is the forward-looking user input area. `prompt.md` and
  `run_config.yaml` are the canonical entrypoints going forward.
- `input/agent_task.md` and `input/agent_scaffold.md` are kept as transitional
  files during the repository migration. They are not the official contract for
  the MVP scaffold.
- `input_data/` stores local datasets used for sandbox runs. New dataset drops are
  ignored by git.
- `codex-main/` is an upstream Codex-like source snapshot.
- `vscode-main/` is an upstream Code OSS / VS Code source snapshot.

## Upstream boundaries

`codex-main/` and `vscode-main/` are treated as vendored upstream sources.
Early Gauntlet work should avoid direct invasive edits in those trees. New Gauntlet
behavior should be introduced through thin adapters, Gauntlet-owned manifests, and
new documentation in the project root instead.

## MVP focus

The first vertical slice centers on `gauntlet-sandbox/` rather than on a full IDE
rewrite. The immediate goal is to define the contract that later work will execute:

- user prompt input
- dataset input
- a fixed six-step pipeline
- explicit artifact locations
- a human-edited project manifest

This keeps the early prototype small, testable, and reproducible.

## Adapter-first rule

Gauntlet should add project-specific layers around upstream systems before any deep
integration work begins. In practice, that means:

- define stable config and artifact contracts first
- add Gauntlet-owned docs and manifests first
- defer workbench and agent-core integration until those contracts exist
- prefer wrappers and adapters over upstream rewrites

