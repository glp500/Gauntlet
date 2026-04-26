# Coding Task Plan: Local Agent-Driven Analysis Sandbox

## Goal

Build a local Python program that runs with `python start.py`, reads a task from `inputs/input.txt` plus one or more CSV files, routes work between OpenAI and Ollama, generates a constrained analysis code bundle inside a per-run sandbox, executes that code, and saves artifacts such as figures, result CSVs, logs, and generated scripts.

## v1 Scope

The first version should support one workflow well:

1. Read `input.txt` and CSV files from a fixed input folder.
2. Refine the task into a structured analysis brief.
3. Generate a fixed set of Python files for the sandbox.
4. Run the generated code in an isolated per-run workspace.
5. Save outputs to predictable folders.
6. Preserve logs and intermediate artifacts for debugging.

Out of scope for v1:

- Arbitrary repo-wide file editing
- Open-ended autonomous shell use
- Broad browser autonomy
- Long-lived multi-run memory
- Dynamic file creation beyond the allowed sandbox contract

## Key Inputs And Constraints

- User entrypoint is a local CLI command: `python start.py`
- Inputs live in a predictable folder structure and include:
  - `input.txt`
  - One or more CSV data files
- The system should support agent-style delegation and tool use
- Default model routing should use the OpenAI API with `gpt-5.4-mini-2026-03-17`
- Secondary routing should use a local Ollama endpoint
- The sandbox must be:
  - Free
  - Local
  - Open source
  - Constrained
  - Repeatable
- Generated code should stay tightly scoped to a small file set rather than sprawling across arbitrary files
- Initial sandbox template should include:
  - `data_loader.py`
  - `preprocessing.py`
  - `analysis.py`
  - `figures.py`
- Expected outputs include generated figures and CSV result files

## Assumptions

- This is a developer tool for analysis workflows, not a general-purpose autonomous coding agent.
- The first version should optimize for reliability and inspectability over autonomy.
- The main workload is structured data analysis on CSVs, with Python as the primary execution language.
- The agent system should generate or edit a known set of Python files, then run them in a controlled environment.
- Web search is a callable tool, not unrestricted browser autonomy by default.
- LangChain is currently a candidate orchestration layer, not a final requirement.

## Architecture

Use a simple coordinator-driven pipeline rather than a heavy agent graph unless research proves a framework is clearly worth it.

Suggested flow:

1. `start.py` parses config and starts a run.
2. Input loader reads `input.txt` and CSV file metadata.
3. Prompt refiner turns the raw task into a structured analysis brief.
4. Router selects the model or backend for each step.
5. Code generator produces the allowed sandbox files.
6. Code reviewer checks structure, readability, and sandbox compliance.
7. Sandbox manager creates a fresh run workspace from the template.
8. Executor runs the generated pipeline and captures logs.
9. Artifact collector gathers figures, CSV outputs, and run summary.

## Recommended Folder Layout

```text
project/
  start.py
  requirements.txt
  README.md

  inputs/
    input.txt
    data/
      *.csv

  sandbox_template/
    data_loader.py
    preprocessing.py
    analysis.py
    figures.py
    run_analysis.py
    requirements.txt

  src/
    config.py
    models.py
    run_context.py

    orchestrator/
      pipeline.py
      prompt_refiner.py
      router.py
      code_generator.py
      code_reviewer.py

    sandbox/
      manager.py
      executor.py
      file_policy.py

    io/
      input_loader.py
      artifact_collector.py
      summary_writer.py

    tools/
      schemas.py
      registry.py
      file_tools.py
      exec_tools.py
      web_tools.py

    llm/
      base.py
      openai_client.py
      ollama_client.py

    logging/
      setup.py

  workspace_runs/
    <run_id>/
      sandbox/
      outputs/
      logs/
      prompts/
      responses/
      metadata.json

  outputs/
    latest/
```

## Run Contract

### Input Contract

- `inputs/input.txt` must exist.
- `inputs/data/` contains one or more CSV files.
- The program should fail clearly if either is missing.

### Output Contract Per Run

- Generated sandbox code
- Execution logs
- Result CSVs
- Figures
- Run summary
- Metadata showing model or backend selection

Suggested run output shape:

```text
workspace_runs/<run_id>/
  sandbox/
    data_loader.py
    preprocessing.py
    analysis.py
    figures.py
    run_analysis.py
  outputs/
    results/
      *.csv
    figures/
      *.png
    summary.json
  logs/
    pipeline.log
    execution.log
  prompts/
    refined_prompt.txt
    codegen_prompt.txt
  responses/
    codegen_response.json
    review_response.json
  metadata.json
```

## Sandbox File Contract

The model may only generate or modify:

- `data_loader.py`
- `preprocessing.py`
- `analysis.py`
- `figures.py`

The runtime owns:

- `run_analysis.py`
- Dependency installation strategy
- Execution wrapper
- Output directories

Role of each generated file:

- `data_loader.py`
  - Load CSV files
  - Validate expected columns where possible
  - Return pandas DataFrames or a structured input object
- `preprocessing.py`
  - Clean and transform input data
  - Keep transformations explicit and readable
- `analysis.py`
  - Compute statistics, derived tables, and result datasets
  - Write structured outputs for downstream use
- `figures.py`
  - Generate plots from processed or analysis outputs
  - Save figures into the run's `outputs/figures/`
- `run_analysis.py`
  - Call the above modules in order
  - Manage paths
  - Capture and persist outputs
  - Remain fixed and human-authored

## Module Interfaces

Keep interfaces small and explicit.

Example interface contract:

```python
# data_loader.py
def load_data(input_dir: str) -> dict[str, "pd.DataFrame"]:
    """Load all CSV inputs from the sandbox input directory."""

# preprocessing.py
def preprocess(data: dict[str, "pd.DataFrame"]) -> dict[str, "pd.DataFrame"]:
    """Return cleaned or transformed data frames."""

# analysis.py
def run_analysis(data: dict[str, "pd.DataFrame"]) -> dict[str, "pd.DataFrame"]:
    """Return result tables to be written as CSV files."""

# figures.py
def create_figures(
    data: dict[str, "pd.DataFrame"],
    results: dict[str, "pd.DataFrame"],
    output_dir: str,
) -> list[str]:
    """Create figures and return written file paths."""
```

## Model Routing Spec

Primary backend:

- OpenAI using `gpt-5.4-mini-2026-03-17`

Secondary backend:

- Local Ollama endpoint

Routing policy for v1:

- Prompt refinement: OpenAI
- Code generation: OpenAI by default
- Review pass: OpenAI or Ollama
- Fallback on backend failure: Ollama only for low-risk text steps, not final authority unless explicitly configured

Use a shared backend interface:

```python
class LLMBackend(Protocol):
    def generate(self, system_prompt: str, user_prompt: str, **kwargs) -> dict:
        ...
```

Normalized response shape should include:

- `content`
- `model`
- `backend`
- `usage` if available
- `raw_response`

## Prompting Rules

The code generation prompt should strongly constrain the model:

- Only write the four allowed files
- Do not create helpers unless necessary
- Use pandas and matplotlib unless configured otherwise
- No network access
- No shell commands inside generated code
- Keep code readable and explicit
- Add comments only for non-obvious logic
- Preserve clear separation between loading, preprocessing, analysis, and figure generation

The review prompt should check:

- File role compliance
- Readability
- Dependency realism
- No sandbox violations
- No extra files
- No hidden execution behavior

## Sandbox Spec

For v1, use a fresh per-run workspace with deterministic paths and subprocess-based execution. If Docker or `nsjail` is adopted, keep that behind the sandbox manager so the rest of the app does not care.

Minimum sandbox behavior:

- Copy `sandbox_template/` into `workspace_runs/<run_id>/sandbox/`
- Copy or mount input CSV files into the run workspace
- Write generated files into the sandbox
- Run `run_analysis.py`
- Enforce:
  - Timeout
  - Working-directory restriction
  - Captured stdout and stderr
  - Bounded output size

Nice-to-have for v1.1:

- No-network enforcement
- Package whitelist
- Process and memory limits

## Tool Surface

Keep tools minimal and explicit.

Suggested internal tools:

- `read_input_manifest`
- `list_input_files`
- `write_allowed_sandbox_files`
- `review_generated_bundle`
- `execute_sandbox`
- `collect_artifacts`
- `fetch_web_context` only if explicitly enabled

Web access should be off by default.

## Config

Suggested config file or environment settings:

- `OPENAI_API_KEY`
- `OPENAI_MODEL=gpt-5.4-mini-2026-03-17`
- `OLLAMA_BASE_URL=http://localhost:11434`
- `OLLAMA_MODEL=<chosen-model>`
- `RUN_TIMEOUT_SECONDS=120`
- `MAX_REVIEW_ROUNDS=1`
- `ENABLE_WEB=false`

## Research To Complete First

1. OpenAI API orchestration
   - Confirm current API patterns for model routing, tool calling, structured outputs, and multi-step loops.
   - Validate best practices for `gpt-5.4-mini-2026-03-17`.
   - Check retries, limits, and cost controls.
2. Local model fallback via Ollama
   - Review the local HTTP API, model management, streaming, timeouts, and error handling.
   - Decide which tasks are safe to route to Ollama.
3. Agent framework choice
   - Compare LangChain, LangGraph, and a lightweight custom orchestration loop.
   - Focus on routing, tool calling, delegation, state handling, and observability.
4. Sandbox strategy
   - Compare `venv` plus filesystem controls, Docker, `nsjail`, and Firejail.
   - Evaluate setup burden, reproducibility, isolation, and debugging.
5. Web search tool
   - Define whether this is search, targeted page fetch, or browser automation.
   - Clarify whether Playwright is only for browsing and extraction.
6. Code execution architecture
   - Review generated-code pipeline patterns for validation, execution, and artifact capture.

## Validation Strategy

At minimum:

- Unit tests for routing, input discovery, file policy, and artifact collection
- Integration test for one known CSV task
- Failure-path tests for missing files, malformed CSVs, backend failure, and sandbox timeout

Add a review checklist to implementation:

- Readable before clever
- Explicit file boundaries
- No generic utility sprawl
- No fake agent abstractions that hide a simple pipeline
- Log enough to debug a failed run

## Risks And Open Questions

- Framework choice: a custom orchestration loop may be cleaner than LangChain if the workflow is narrow.
- Sandbox depth: true isolation may push the design toward Docker or jail-based tooling; a lighter filesystem sandbox is easier but weaker.
- Web search is still underspecified. Playwright is not itself a search engine.
- Model routing policy still needs sharper rules around when Ollama is acceptable.
- Generated code governance needs a hard rule on allowed dependencies.
- It is still unclear whether the agent should only create analysis code or also create the script that executes the pipeline.
- Cross-platform expectations are unstated, and sandbox choice may depend heavily on that.

## Execution Ticket Set

### Ticket 1: Lock the v1 Architecture

**Objective**

Decide the orchestration and sandbox approach for v1.

**Tasks**

- Compare custom orchestration vs LangChain or LangGraph
- Compare subprocess workspace sandbox vs Docker vs `nsjail`
- Choose the Ollama fallback model
- Write a short ADR-style design note

**Acceptance Criteria**

- One documented choice for orchestration
- One documented choice for sandboxing
- One documented routing policy
- Clear statement of non-goals for v1

### Ticket 2: Create the Project Skeleton

**Objective**

Set up the repo structure and core modules.

**Tasks**

- Add `start.py`, `src/` package layout, `sandbox_template/`, and `inputs/`
- Add config loading and logging setup
- Add a sample `input.txt` and demo CSV

**Acceptance Criteria**

- Running `python start.py` reaches the main pipeline entry without crashing
- The folder structure matches the agreed spec
- Logging and config load successfully

### Ticket 3: Implement Input Discovery and Run Context

**Objective**

Load user inputs and create a reproducible run directory.

**Tasks**

- Validate presence of `inputs/input.txt`
- Discover CSVs under `inputs/data/`
- Create a `run_id`
- Build `workspace_runs/<run_id>/` layout
- Persist run metadata

**Acceptance Criteria**

- Missing input cases fail with clear messages
- Valid input creates a run workspace and metadata file
- Input manifest is logged and available to later pipeline steps

### Ticket 4: Add OpenAI Backend

**Objective**

Implement the primary LLM backend.

**Tasks**

- Build an OpenAI client wrapper
- Normalize responses into a shared schema
- Add timeout, retry, and error handling
- Log model and backend metadata

**Acceptance Criteria**

- Prompt refinement and code generation calls can be made through one backend interface
- Failures are surfaced cleanly
- Backend selection is recorded in run metadata

### Ticket 5: Add Ollama Backend

**Objective**

Implement the local fallback backend.

**Tasks**

- Build an Ollama client wrapper
- Match the same normalized response schema
- Add health check and connection error handling
- Make backend configurable

**Acceptance Criteria**

- Ollama can respond through the same interface as OpenAI
- An unavailable local endpoint produces a clear, non-cryptic error
- The router can choose Ollama for a supported step

### Ticket 6: Build the Router

**Objective**

Route pipeline steps to the right backend.

**Tasks**

- Define step types such as `refine_prompt`, `generate_code`, and `review_code`
- Add routing rules and fallback logic
- Record the chosen backend per step

**Acceptance Criteria**

- Given a step type, the router picks the expected backend
- Fallback behavior is deterministic and logged
- Unsupported fallback cases fail safely

### Ticket 7: Implement Prompt Refinement

**Objective**

Turn raw user input into a structured analysis brief.

**Tasks**

- Read `input.txt` and CSV metadata
- Create a refinement prompt
- Save the refined brief to the run folder

**Acceptance Criteria**

- The program produces a structured refined prompt artifact
- The output includes analysis goals, input summary, and code constraints
- The result is suitable for code generation without manual editing

### Ticket 8: Build Constrained Code Generation

**Objective**

Generate only the allowed sandbox files.

**Tasks**

- Create the code generation prompt with file-role instructions
- Parse the model response into file contents
- Reject extra files or malformed outputs
- Write approved files into the sandbox workspace

**Acceptance Criteria**

- Only `data_loader.py`, `preprocessing.py`, `analysis.py`, and `figures.py` are generated
- Extra-file attempts are rejected
- Generated files are saved and readable

### Ticket 9: Build Review Pass

**Objective**

Check the generated bundle before execution.

**Tasks**

- Implement a review prompt or rule-based checker
- Validate file role boundaries and dependency usage
- Surface warnings or block execution on severe violations

**Acceptance Criteria**

- Review output is saved
- Severe policy violations stop execution
- Benign comments are logged without blocking the run

### Ticket 10: Build Sandbox Manager

**Objective**

Create and manage the isolated per-run workspace.

**Tasks**

- Copy the template into the run sandbox
- Copy or expose input files inside the run
- Enforce allowed file writes
- Prepare output directories

**Acceptance Criteria**

- Each run gets a clean sandbox directory
- The sandbox contains the fixed template and generated files
- Input and output paths are deterministic

### Ticket 11: Build Executor

**Objective**

Run the generated analysis pipeline safely and capture outputs.

**Tasks**

- Execute `run_analysis.py` from the sandbox
- Capture stdout, stderr, exit code, and runtime
- Enforce timeout
- Write execution logs

**Acceptance Criteria**

- Successful runs produce exit code, logs, and output artifacts
- Timed-out or failed runs produce clear failure logs
- The executor does not write outside the run workspace

### Ticket 12: Collect Artifacts and Write Summary

**Objective**

Turn raw run outputs into a clean result package.

**Tasks**

- Gather figure files and result CSVs
- Write a summary JSON or text report
- Copy or link the latest outputs into `outputs/latest/`

**Acceptance Criteria**

- Outputs are easy to find
- Summary includes status, model usage, produced files, and failure reason if applicable
- `outputs/latest/` reflects the most recent run

### Ticket 13: Add Tests

**Objective**

Cover the core pipeline and known failure modes.

**Tasks**

- Unit tests for config, routing, file policy, and input loader
- Integration test for one complete CSV analysis run
- Failure-path tests for missing files, malformed CSV, backend error, and timeout

**Acceptance Criteria**

- Happy-path test passes locally
- Known failure modes return readable errors
- Tests are scoped and maintainable

### Ticket 14: Polish for Maintainability

**Objective**

Make the codebase easy to extend without inflating it.

**Tasks**

- Remove premature abstractions
- Improve naming and module boundaries
- Add concise docstrings where they help
- Review logs and error messages for clarity

**Acceptance Criteria**

- The pipeline is easy to follow from `start.py`
- Core logic is in small, readable modules
- No unnecessary helper layers or fallback sprawl remain

## Suggested Build Order

1. Tickets 1 through 3
2. Tickets 4 through 7
3. Tickets 8 through 12
4. Tickets 13 and 14

## Recommended Next Step

Start with Ticket 1 and make two hard decisions early:

1. Custom loop vs LangChain or LangGraph
2. Lightweight sandbox vs stronger isolation

Those choices will shape almost every other file in the project.
