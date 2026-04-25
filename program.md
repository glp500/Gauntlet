# Gauntlet `program.md`

Status: planning specification for coding-agent implementation  
Repository: `glp500/Gauntlet`  
Project working name: **Gauntlet**  
Product thesis: **a safe, agentic data-science IDE that turns a prompt plus data into reproducible data loading, preprocessing, analysis, training, evaluation, and editable visual figures.**

---

## 1. Executive summary

Gauntlet is an IDE for data science and scientific computing that combines:

1. a VS Code-derived workbench,
2. a Codex-like agent loop,
3. a restricted sandbox runtime for generated scripts,
4. a reproducible data-science pipeline,
5. an editable visualization layer where manual figure edits can be translated back into code.

The MVP should not attempt to build a full new IDE all at once. The first version should prove a narrow but complete loop:

> User provides a prompt and dataset or data link → agent plans analysis → agent writes or updates pipeline scripts inside `gauntlet-sandbox` → sandbox executes scripts → UI shows data preview, analysis output, model metrics, and visual figures → user edits a figure through a visual editor → Gauntlet records the edit as structured figure operations → generated visualization code is updated to reproduce the manual edits.

The project already contains large upstream codebases and empty pipeline files. The immediate task is to **extract stable interfaces**, not to modify all upstream source at once.

---

## 2. Current repository observations

The current repo appears to contain these top-level areas:

```text
Gauntlet/
  codex-main/          # upstream OpenAI Codex-like agent source snapshot
  vscode-main/         # upstream Code OSS / VS Code source snapshot
  gauntlet-sandbox/    # intended generated-script sandbox
  input/               # likely user prompt/config input area
  input_data/          # likely user dataset area
```

`gauntlet-sandbox/` currently contains the intended data-science workflow modules:

```text
gauntlet-sandbox/
  data_loader.py
  data_preprocessing.py
  analysis.py
  train.py
  eval.py
  visualization.py
```

Those files should become the first stable MVP target. The coding agent should scaffold the project around them instead of replacing them with a monolithic script.

---

## 3. Product definition

### 3.1 One-sentence product definition

Gauntlet is a secure, reproducible, agentic data-science IDE that lets users load data, run analyses, train models, evaluate results, and edit visualizations while preserving executable code as the source of truth.

### 3.2 Primary user

Initial target user:

- scientist, researcher, ML student, or data scientist
- has a dataset or data link
- wants a reliable exploratory-to-modeling pipeline
- may not want to manually write boilerplate data loading, cleaning, plotting, and evaluation code
- needs results that are reproducible, auditable, and editable

### 3.3 Core user stories

1. **Prompt-to-analysis**
   - As a user, I can provide a natural-language prompt and a dataset.
   - Gauntlet plans a data workflow and generates code in sandboxed modules.
   - Gauntlet runs the workflow and shows structured outputs.

2. **Data inspection**
   - As a user, I can preview the loaded data, schema, missing values, summary statistics, and inferred task type.

3. **Preprocessing**
   - As a user, I can let the agent create a preprocessing pipeline with explicit, reviewable transformations.

4. **Model training**
   - As a user, I can ask Gauntlet to train a baseline model appropriate for the inferred or specified task.

5. **Evaluation**
   - As a user, I can inspect model metrics and generated evaluation artifacts.

6. **Editable figures**
   - As a user, I can manually edit generated charts and figures.
   - Gauntlet records those edits as structured operations and reflects them back into the visualization code.

7. **Reproducibility**
   - As a user, I can rerun the same workflow and reproduce outputs from a saved project manifest.

8. **Safe execution**
   - As a user, I can trust that generated code runs in a constrained environment with explicit file, network, dependency, and shell-command policies.

---

## 4. Non-goals for the first MVP

Do not attempt these in the first implementation pass:

- full replacement of VS Code internals
- full replacement of Codex internals
- local fine-tuned model agents
- arbitrary multi-language data pipelines
- production cloud execution
- real-time collaborative editing
- fully general Photoshop/Illustrator-level figure editing
- uncontrolled package installation by the model
- unrestricted shell command execution
- automatic model training on massive datasets
- polished marketplace extension support

The MVP should focus on a narrow, testable local loop.

---

## 5. Design principles

1. **Code remains the source of truth**
   - Every generated result must map back to scripts, configuration, and run metadata.

2. **Structured state over hidden agent memory**
   - Use explicit manifests, schemas, JSON logs, and run artifacts.
   - Avoid relying on opaque conversation state for reproducibility.

3. **Adapters before rewrites**
   - Do not directly fuse VS Code and Codex with broad invasive edits.
   - Create adapter layers between the workbench, agent loop, sandbox runner, and figure editor.

4. **Sandbox first**
   - Generated code must run in a constrained Gauntlet runtime before it is exposed as trusted output.

5. **Human-editable, agent-replayable**
   - Manual UI edits should become structured operations that the agent and code generator can replay.

6. **Small vertical slices**
   - Ship one end-to-end path before expanding features horizontally.

---

## 6. Recommended branch strategy

Use **feature branches by task or vertical slice**, not branches per collaborator and not permanent branches per component.

### 6.0 Required local working branch

All early local development for this repository must happen on:

```text
early-prototype
```

The coding agent must **not** push work directly to `main`.

Before editing files, the agent must check the active branch:

```bash
git branch --show-current
```

If the branch is not `early-prototype`, the agent must switch to it or create it:

```bash
git fetch origin
git checkout early-prototype || git checkout -b early-prototype
```

When pushing, the agent must push explicitly to `origin early-prototype`:

```bash
git push -u origin early-prototype
```

Do not use:

```bash
git push origin main
git push
```

unless the user explicitly instructs the agent to do so after review.

Feature branches may still be used for individual tasks, but their base branch should be `early-prototype`, not `main`:

```text
early-prototype
feature/sandbox-run-manifest
feature/agent-tool-registry
feature/figures-json-ir
```

Pull requests should target `early-prototype` during early development. Merge into `main` only when the project reaches a reviewed milestone.

### 6.1 Why not collaborator branches?

Collaborator branches become ambiguous and long-lived. They make it hard to understand what changed, why it changed, and when it should merge.

### 6.2 Why not permanent component branches?

Permanent component branches such as `agent-core`, `sandbox`, and `figure-editor` drift apart and create painful integration work. Component ownership should live in folders, CODEOWNERS, labels, and review rules, not in permanent branches.

### 6.3 Recommended model

```text
main                        # protected, always buildable
feature/<area>-<slug>       # normal work branches
spike/<area>-<question>     # experiments; may be discarded
integration/<milestone>     # temporary only when a large milestone needs coordinated merging
release/<version>           # later, once packaging exists
hotfix/<slug>               # later, once users exist
```

Examples:

```text
feature/sandbox-run-manifest
feature/agent-tool-registry
feature/figures-json-ir
feature/workbench-results-panel
spike/codex-callgraph-extractor
spike/figma-mcp-design-context
integration/mvp-vertical-slice
```

### 6.4 Pull request rules

Each PR should include:

- purpose
- linked milestone
- changed package or subsystem
- test evidence
- screenshots or logs when UI/runtime behavior changes
- explicit migration note if repo structure changes

### 6.5 Protected branch requirements

`main` should require:

- format/lint pass
- TypeScript build pass where applicable
- Rust build/test pass where applicable
- Python unit tests for sandbox modules
- no secret files
- license checks for upstream source usage
- at least one review once collaborators join

---

## 7. Target repository scaffolding

The current repo contains upstream snapshots. Add a clean Gauntlet layer that isolates project-specific code.

Recommended future structure:

```text
Gauntlet/
  program.md

  apps/
    gauntlet-ide/
      package.json
      src/
        extension/
        workbench/
        panels/
          prompt-panel/
          data-preview-panel/
          run-results-panel/
          figure-editor-panel/
        main.ts

  packages/
    agent-core/
      src/
        agent_loop.ts
        planner.ts
        policy.ts
        model_provider.ts
        openai_provider.ts
        local_provider.ts
        messages.ts
      tests/

    tool-registry/
      src/
        tool_schema.ts
        tool_dictionary.ts
        tool_runner.ts
        tools/
          load_dataset.ts
          inspect_schema.ts
          write_pipeline_file.ts
          run_sandbox_step.ts
          read_artifact.ts
          update_figure_spec.ts
      schemas/
        tool.schema.json
        tool-call.schema.json
      tests/

    codex-adapter/
      src/
        codex_action_extractor.ts
        codex_callgraph.ts
        codex_action_dictionary.ts
      output/
        codex-actions.generated.json
        codex-callgraph.generated.json
      tests/

    vscode-adapter/
      src/
        commands.ts
        panels.ts
        file_watchers.ts
        custom_editors.ts
        terminals.ts
      tests/

    sandbox-runner/
      src/
        runner.ts
        manifest.ts
        process_policy.ts
        artifact_collector.ts
        environment.ts
      tests/

    data-kernel/
      python/
        gauntlet_data/
          __init__.py
          io.py
          schema.py
          preprocess.py
          analysis.py
          train.py
          evaluate.py
          visualize.py
          report.py
        tests/
      pyproject.toml

    figure-model/
      src/
        figure_document.ts
        figure_operations.ts
        figure_patch.ts
        codegen.ts
      schemas/
        figure-document.schema.json
        figure-operation.schema.json
      tests/

    figure-editor/
      src/
        canvas/
        inspector/
        layer_tree/
        properties_panel/
        bindings_panel/
      tests/

    design-pipeline/
      src/
        figma_client.ts
        figma_tokens.ts
        figma_mcp_notes.md
        design_manifest.ts
      tests/

    observability/
      src/
        events.ts
        run_log.ts
        traces.ts

  gauntlet-sandbox/
    README.md
    gauntlet.yaml
    data_loader.py
    data_preprocessing.py
    analysis.py
    train.py
    eval.py
    visualization.py
    outputs/
      .gitkeep

  input/
    prompt.md
    run_config.yaml

  input_data/
    .gitkeep

  docs/
    architecture/
      overview.md
      agent-loop.md
      sandbox.md
      figure-editing.md
      figma-pipeline.md
      security.md
    decisions/
      ADR-0001-branch-strategy.md
      ADR-0002-adapter-first-architecture.md
      ADR-0003-figure-ir.md
    milestones/
      mvp.md
      post-mvp.md

  scripts/
    inventory_repo.ts
    extract_codex_actions.ts
    build_codex_callgraph.ts
    run_gauntlet_sandbox.ts
    check_licenses.ts

  tests/
    fixtures/
      tabular_classification/
      tabular_regression/
      time_series/
    e2e/
      prompt_to_report.test.ts

  codex-main/       # upstream snapshot; minimize direct modifications
  vscode-main/      # upstream snapshot; minimize direct modifications
```

---

## 8. System architecture

### 8.1 High-level architecture

```text
User Prompt + Dataset
        |
        v
Gauntlet Workbench UI
        |
        v
Agent Orchestrator
        |
        +--> Tool Registry
        |       +--> Dataset tools
        |       +--> File-writing tools
        |       +--> Sandbox execution tools
        |       +--> Artifact-reading tools
        |       +--> Figure-editing tools
        |
        +--> Model Provider
        |       +--> OpenAI API provider for MVP
        |       +--> Local model provider later
        |
        v
Sandbox Runner
        |
        v
Pipeline Scripts
        |
        v
Run Artifacts
        |
        +--> Data previews
        +--> Analysis summaries
        +--> Model metrics
        +--> Figures
        +--> Figure documents
        +--> Run manifest
        |
        v
Workbench Result Panels + Figure Editor
```

### 8.2 Main components

#### Workbench shell

Initial approach:

- use the existing `vscode-main` source as the UI/workbench base
- prefer extension-like integration first
- add custom panels for prompt input, run status, data preview, result artifacts, and figure editing
- avoid broad modifications to VS Code core until interfaces are validated

#### Agent orchestrator

Responsibilities:

- receive user prompt and project context
- infer task type
- create a structured execution plan
- select tools from the tool registry
- generate or patch code
- request sandbox runs
- inspect artifacts and errors
- iterate until success or policy limit
- emit final report state

#### Tool registry

Responsibilities:

- expose a finite list of allowed actions
- define schemas for tool inputs and outputs
- validate every model-requested action
- route tool calls to host-side code
- log all actions and outputs

#### Sandbox runner

Responsibilities:

- execute generated Python scripts
- constrain filesystem access
- constrain network access
- set resource limits
- capture stdout, stderr, exit codes, artifacts, and metadata
- produce a run manifest

#### Data kernel

Responsibilities:

- provide reusable Python utilities for data loading, inspection, preprocessing, training, evaluation, and visualization
- reduce the amount of ad hoc generated code
- make agent outputs more reliable by encouraging calls into known helpers

#### Figure model and editor

Responsibilities:

- represent figures as structured JSON
- preserve a mapping between figure elements and visualization code
- capture manual edits as operations
- regenerate visualization code from the edited figure spec
- keep rendered output, figure spec, and source code synchronized

#### Figma/design pipeline

Responsibilities:

- ingest design tokens, frames, components, and layout context from Figma
- store design manifests locally
- use Figma only as a design source-of-truth and prototype review loop for MVP
- later, use MCP or API integrations for bidirectional design-code iteration

---

## 9. Data-science pipeline contract

The sandbox should expose a fixed pipeline contract. Each module has one clear responsibility.

```text
data_loader.py
  load_data(config) -> LoadedData

data_preprocessing.py
  preprocess(data, config) -> PreprocessedData

analysis.py
  analyze(data, config) -> AnalysisArtifacts

train.py
  train_model(data, config) -> ModelArtifacts

eval.py
  evaluate(model, data, config) -> EvaluationArtifacts

visualization.py
  create_visualizations(data, analysis, evaluation, config) -> FigureArtifacts
```

### 9.1 Initial artifact layout

```text
gauntlet-sandbox/
  outputs/
    run_manifest.json
    data_profile.json
    preprocessing_report.json
    analysis_summary.md
    model_metrics.json
    figures/
      figure_001.json
      figure_001.svg
      figure_001.png
      figure_001.py
    report.md
```

### 9.2 `gauntlet.yaml`

Add a run manifest config:

```yaml
project:
  name: gauntlet-demo
  task: auto
  created_by: gauntlet

input:
  prompt_file: ../input/prompt.md
  data:
    type: local_file
    path: ../input_data/dataset.csv

runtime:
  python: "3.11"
  allow_network: false
  max_runtime_seconds: 120
  max_memory_mb: 4096
  max_output_mb: 256

pipeline:
  steps:
    - data_loader
    - data_preprocessing
    - analysis
    - train
    - eval
    - visualization

modeling:
  baseline_only: true
  train_test_split: 0.2
  random_seed: 42

figures:
  output_format:
    - svg
    - png
    - json
  editable: true
```

---

## 10. Agent architecture

### 10.1 MVP agent loop

The MVP agent loop should be explicit and inspectable.

```text
1. Receive prompt and dataset reference.
2. Build project context.
3. Inspect dataset schema.
4. Produce a plan.
5. Write or patch pipeline files.
6. Run one pipeline step.
7. Read artifacts and errors.
8. Patch code if needed.
9. Continue until all MVP steps pass or a limit is reached.
10. Summarize outputs and expose artifacts in the UI.
```

### 10.2 Agent roles

MVP should use one model with role prompts, not multiple concurrent autonomous agents. Later versions can split these into specialized agents.

Initial logical roles:

- **Planner**: converts user prompt into a pipeline plan
- **Coder**: writes or patches Python modules
- **Runner**: requests sandbox execution
- **Debugger**: interprets errors and proposes fixes
- **Reporter**: produces final summary
- **Figure editor translator**: converts figure operations into visualization code patches

Future specialized agents:

- data loader agent
- preprocessing agent
- statistical analysis agent
- model-training agent
- evaluation agent
- visualization agent
- paper-quality figure agent
- code-review agent
- sandbox policy agent

### 10.3 Provider abstraction

Create a provider interface now so the MVP can use OpenAI API endpoints and later switch to local models.

```ts
export interface ModelProvider {
  name: string;
  generate(request: ModelRequest): Promise<ModelResponse>;
  supportsTools: boolean;
  supportsStructuredOutput: boolean;
}
```

Implement:

```text
OpenAIProvider       # MVP
LocalProvider        # placeholder for future local inference
MockProvider         # deterministic tests
```

---

## 11. Tool-call dictionary

The “flowchart style dictionary of tool calls and functions” should be a first-class artifact.

### 11.1 Tool dictionary schema

```ts
type ToolDefinition = {
  name: string;
  category:
    | "project"
    | "data"
    | "code"
    | "sandbox"
    | "artifact"
    | "figure"
    | "design"
    | "safety";
  description: string;
  input_schema: object;
  output_schema: object;
  policy: {
    requires_confirmation: boolean;
    allowed_in_mvp: boolean;
    sandbox_only: boolean;
    network_access: "never" | "ask" | "allowed";
    writes_files: boolean;
  };
};
```

### 11.2 MVP tool list

```text
project.read_manifest
project.write_manifest
project.read_prompt
project.update_status

data.locate_input
data.load_preview
data.infer_schema
data.profile
data.sample_rows

code.read_file
code.write_file
code.apply_patch
code.format_python
code.list_pipeline_files

sandbox.run_step
sandbox.run_pipeline
sandbox.read_stdout
sandbox.read_stderr
sandbox.stop_run

artifact.list
artifact.read_json
artifact.read_markdown
artifact.read_image_metadata

figure.create_spec
figure.render
figure.apply_operation
figure.generate_code_patch
figure.export_svg
figure.export_png

safety.validate_path
safety.validate_dependency
safety.validate_command
safety.redact_secret
```

### 11.3 Future tool list

```text
figma.fetch_file
figma.fetch_nodes
figma.fetch_tokens
figma.sync_design_manifest
figma.send_ui_snapshot

model.local_load
model.local_infer
model.local_finetune_job

data.connect_database
data.connect_url
data.validate_license
data.generate_synthetic_preview

notebook.export
report.export_pdf
report.export_latex
```

### 11.4 Example tool definition

```json
{
  "name": "sandbox.run_step",
  "category": "sandbox",
  "description": "Run one named Gauntlet pipeline step inside the constrained sandbox.",
  "input_schema": {
    "type": "object",
    "required": ["step_name", "run_id"],
    "properties": {
      "step_name": {
        "type": "string",
        "enum": [
          "data_loader",
          "data_preprocessing",
          "analysis",
          "train",
          "eval",
          "visualization"
        ]
      },
      "run_id": { "type": "string" }
    }
  },
  "output_schema": {
    "type": "object",
    "required": ["exit_code", "stdout_path", "stderr_path", "artifacts"],
    "properties": {
      "exit_code": { "type": "integer" },
      "stdout_path": { "type": "string" },
      "stderr_path": { "type": "string" },
      "artifacts": {
        "type": "array",
        "items": { "type": "string" }
      }
    }
  },
  "policy": {
    "requires_confirmation": false,
    "allowed_in_mvp": true,
    "sandbox_only": true,
    "network_access": "never",
    "writes_files": true
  }
}
```

---

## 12. Codex source extraction plan

The goal is not to blindly copy Codex internals into Gauntlet. The goal is to learn and reuse the useful architectural patterns.

### 12.1 Stage A: inventory

Create:

```text
scripts/inventory_repo.ts
```

Output:

```text
docs/generated/repo-inventory.md
docs/generated/codex-inventory.md
docs/generated/vscode-inventory.md
```

The inventory should include:

- packages/modules
- command entrypoints
- tool-call related code
- sandbox-related code
- model provider code
- approval/policy code
- TUI/IDE integration code
- test structure
- dependency graph summary

### 12.2 Stage B: control-flow graph

Create:

```text
scripts/build_codex_callgraph.ts
```

Output:

```text
packages/codex-adapter/output/codex-callgraph.generated.json
docs/generated/codex-callgraph.md
```

The call graph should capture:

- command entrypoints
- agent loop functions
- model request construction
- tool-call parsing
- approval gates
- patch application
- shell execution
- sandbox/policy boundaries
- artifact output paths

### 12.3 Stage C: action dictionary

Create:

```text
scripts/extract_codex_actions.ts
```

Output:

```text
packages/codex-adapter/output/codex-actions.generated.json
docs/generated/codex-actions.md
```

The generated dictionary should not become the product API. It should inform the Gauntlet-specific tool registry.

### 12.4 Stage D: adapter

Create `packages/codex-adapter`, which exposes only stable concepts:

```ts
export interface CodexLikeAgent {
  plan(context: GauntletContext): Promise<GauntletPlan>;
  proposePatch(request: PatchRequest): Promise<PatchProposal>;
  interpretRunFailure(logs: RunLogs): Promise<DebugPlan>;
}
```

Do not import broad Codex internals directly into UI packages. Keep the adapter boundary explicit.

---

## 13. VS Code source integration plan

The goal is to use the VS Code workbench as the base environment, while keeping Gauntlet-specific logic separate.

### 13.1 MVP UI panels

Implement panels or custom views for:

```text
Gauntlet: Prompt
Gauntlet: Data Preview
Gauntlet: Run Plan
Gauntlet: Run Logs
Gauntlet: Results
Gauntlet: Figures
Gauntlet: Figure Inspector
```

### 13.2 Custom editor target

Use a custom editor-like architecture for editable figures.

File extensions:

```text
*.gauntlet-figure.json
*.gauntlet-run.json
```

Initial figure editor responsibilities:

- render SVG/canvas preview
- expose layer tree
- allow title, axis, legend, annotation, color, size, and layout edits
- save edits as JSON operations
- request visualization code regeneration

### 13.3 Integration rule

Do not deeply alter editor internals for the MVP. Add Gauntlet features through extension-style boundaries where possible.

---

## 14. Figure editing architecture

The figure editor is the key differentiator. Treat it as a structured graphics-code synchronization problem.

### 14.1 Figure document

Each figure should have a JSON document:

```json
{
  "version": "0.1",
  "figure_id": "figure_001",
  "source_script": "gauntlet-sandbox/visualization.py",
  "source_function": "create_visualizations",
  "data_bindings": [
    {
      "name": "x",
      "column": "sepal_length",
      "source": "processed_dataframe"
    }
  ],
  "marks": [
    {
      "id": "mark_points",
      "type": "scatter",
      "encoding": {
        "x": "sepal_length",
        "y": "sepal_width",
        "color": "species"
      }
    }
  ],
  "layout": {
    "title": "Sepal length vs width",
    "width": 800,
    "height": 600
  },
  "style": {
    "font_family": "Inter",
    "axis_label_size": 12,
    "title_size": 16
  },
  "operations": []
}
```

### 14.2 Figure operation examples

```json
{
  "op": "set_title",
  "target": "layout.title",
  "value": "Model residuals by prediction"
}
```

```json
{
  "op": "set_axis_label",
  "target": "x_axis.label",
  "value": "Predicted value"
}
```

```json
{
  "op": "add_annotation",
  "target": "figure",
  "value": {
    "x": 0.72,
    "y": 0.18,
    "text": "Outlier cluster",
    "coordinate_system": "normalized"
  }
}
```

### 14.3 MVP editable properties

Start with these only:

- title
- subtitle
- axis labels
- legend title and position
- font sizes
- plot dimensions
- color palette
- point size / line width
- annotation text and position
- export format

Do not implement arbitrary pixel editing in the MVP. Every edit must map to reproducible visualization parameters.

### 14.4 Code synchronization rule

Manual figure edits should update code through a constrained generator:

```text
figure JSON spec + operations
        |
        v
visualization code generator
        |
        v
patch visualization.py
        |
        v
rerun visualization step
        |
        v
new SVG/PNG/JSON artifacts
```

The agent may propose the patch, but the figure-code generator should own deterministic conversions for known operations.

---

## 15. Figma design pipeline

Figma should support product design, UI prototyping, and possibly design-to-code context. It should not block the core data-science MVP.

### 15.1 MVP Figma pipeline

Create:

```text
packages/design-pipeline/
  src/figma_client.ts
  src/design_manifest.ts
  src/figma_tokens.ts
```

Add a local manifest:

```yaml
figma:
  file_key: ""
  pages:
    - Gauntlet MVP
  frames:
    - Prompt Panel
    - Data Preview Panel
    - Results Panel
    - Figure Editor
  tokens:
    colors: true
    typography: true
    spacing: true
```

### 15.2 Figma import goals

- extract design tokens
- extract frame names and hierarchy
- link Figma frames to Gauntlet UI components
- store snapshots under `docs/design/`
- optionally generate UI implementation notes for the coding agent

### 15.3 Figma MCP/API future

Later, support:

- pulling selected frame context into the coding agent
- sending rendered UI snapshots back to Figma as editable frames
- using Figma variables/components as a source of truth for UI consistency

---

## 16. Sandbox and safety design

### 16.1 Threat model

The agent may generate unsafe code accidentally. A malicious prompt or dataset may attempt to:

- read secrets
- access files outside the project
- call the network
- install unsafe packages
- execute shell commands
- exfiltrate data
- consume excessive compute
- hide behavior in generated code

### 16.2 MVP sandbox policy

Default policy:

```yaml
filesystem:
  read_allowlist:
    - input/
    - input_data/
    - gauntlet-sandbox/
  write_allowlist:
    - gauntlet-sandbox/outputs/
    - gauntlet-sandbox/.cache/
  deny:
    - ~/.ssh
    - ~/.config
    - .env
    - "**/*token*"
    - "**/*secret*"

network:
  default: deny
  allow_user_approved_urls: false

process:
  shell: deny_by_default
  python_only: true
  max_runtime_seconds: 120
  max_memory_mb: 4096

dependencies:
  install_new_packages: ask
  allowlist:
    - pandas
    - numpy
    - scipy
    - scikit-learn
    - matplotlib
    - seaborn
    - plotly
    - pyarrow
    - polars
    - pydantic
```

### 16.3 Runtime validation

Before running generated code:

- scan imports
- scan path accesses
- scan subprocess usage
- scan network libraries
- validate output paths
- validate file size limits
- reject obvious secret access patterns

### 16.4 Audit logs

Every run should log:

```json
{
  "run_id": "run_2026_04_25_001",
  "prompt_hash": "...",
  "dataset_hash": "...",
  "model_provider": "openai",
  "tool_calls": [],
  "files_written": [],
  "commands_executed": [],
  "artifacts_created": [],
  "policy_warnings": [],
  "status": "success"
}
```

---

## 17. MVP implementation plan

### Milestone 0: repository baseline

Goal: make the repo understandable and safe for incremental development.

Tasks:

- add `program.md`
- add `docs/architecture/overview.md`
- add `docs/decisions/ADR-0001-branch-strategy.md`
- add `.gitignore` entries for data, outputs, caches, secrets
- add `gauntlet-sandbox/README.md`
- add `gauntlet-sandbox/gauntlet.yaml`
- add basic CI skeleton
- add license inventory script
- document upstream source boundaries

Done when:

- repo has a clear top-level map
- generated outputs are ignored
- first coding agent can follow this document without guessing the project direction

### Milestone 1: sandbox vertical slice

Goal: run the empty pipeline structure with deterministic placeholder outputs.

Tasks:

- implement `scripts/run_gauntlet_sandbox.ts`
- implement `gauntlet-sandbox` Python functions with placeholder logic
- generate `outputs/run_manifest.json`
- generate `outputs/report.md`
- add tests for run manifest creation

Done when:

```bash
pnpm gauntlet:run
```

or equivalent command creates a valid run manifest and report.

### Milestone 2: data loading and profiling

Goal: load a CSV dataset and produce a profile.

Tasks:

- implement `data_loader.py`
- implement schema inference
- implement missing-value summary
- implement numeric/categorical summary
- write `outputs/data_profile.json`
- render data preview in UI or markdown report

Done when:

- user can place a CSV in `input_data/`
- sandbox creates a valid data profile
- failures are clear and recoverable

### Milestone 3: agent tool registry

Goal: expose safe, typed tool calls.

Tasks:

- implement `packages/tool-registry`
- define MVP tool schemas
- implement tool validation
- implement mock model provider tests
- implement OpenAI provider behind an interface
- add tool-call logs to run manifest

Done when:

- model/tool loop can request dataset profile and write a pipeline file through validated tools

### Milestone 4: Codex action extraction

Goal: build a generated understanding of Codex actions.

Tasks:

- create Codex inventory script
- create call graph extraction script
- create generated action dictionary
- create `packages/codex-adapter`
- document which Codex patterns are reused and which are not

Done when:

- `docs/generated/codex-actions.md` exists
- Gauntlet has its own tool registry independent of raw Codex internals

### Milestone 5: prompt-to-pipeline MVP

Goal: user prompt generates and runs a complete baseline workflow.

Tasks:

- read `input/prompt.md`
- inspect dataset profile
- plan pipeline
- generate/patch sandbox scripts
- run pipeline
- debug basic errors
- produce final report

Done when:

- a tabular classification or regression dataset can go from prompt to report without manual code edits

### Milestone 6: workbench result panels

Goal: show outputs inside the VS Code-derived workbench.

Tasks:

- create Gauntlet prompt panel
- create run status panel
- create data preview panel
- create results panel
- create artifact browser
- add command palette commands:
  - `Gauntlet: New Analysis`
  - `Gauntlet: Run Pipeline`
  - `Gauntlet: Open Results`
  - `Gauntlet: Open Figure Editor`

Done when:

- user can run the MVP without manually browsing output files

### Milestone 7: editable figure MVP

Goal: manually edit generated figures and reflect edits back into code.

Tasks:

- define `figure-document.schema.json`
- render a figure document
- implement basic edit operations
- generate code patches for supported operations
- rerun visualization step
- persist changed figure spec and script

Done when:

- user can edit a figure title or axis label visually
- `visualization.py` is patched
- rerunning reproduces the edited figure

### Milestone 8: Figma design bridge

Goal: link UI implementation to Figma designs.

Tasks:

- add Figma design manifest
- extract tokens or manually define first design tokens
- map Figma frames to Gauntlet UI panels
- document Figma-to-code workflow
- optionally add MCP notes and future integration path

Done when:

- UI implementation has a stable design reference and token source

---

## 18. First 10 coding-agent PRs

Use these as the first work queue.

### PR 1 — Project metadata and ignore rules

Branch requirement:

```bash
git branch --show-current
git checkout early-prototype || git checkout -b early-prototype
```

Push requirement:

```bash
git push -u origin early-prototype
```

Do not push this work to `main`.

Create:

```text
program.md
.gitignore
docs/architecture/overview.md
docs/decisions/ADR-0001-branch-strategy.md
```

Ensure:

- `input_data/*` ignored except `.gitkeep`
- `gauntlet-sandbox/outputs/*` ignored except `.gitkeep`
- `.env`, secrets, model caches ignored

### PR 2 — Sandbox README and manifest

Create:

```text
gauntlet-sandbox/README.md
gauntlet-sandbox/gauntlet.yaml
```

Define pipeline contract and artifact layout.

### PR 3 — Placeholder Python pipeline

Implement all sandbox modules with deterministic placeholders.

Each module should be importable and callable. No agent logic yet.

### PR 4 — Sandbox runner script

Create:

```text
scripts/run_gauntlet_sandbox.ts
```

or a Python equivalent if TypeScript bootstrapping is not ready.

It should:

- read `gauntlet.yaml`
- run each pipeline module in order
- collect outputs
- write `run_manifest.json`

### PR 5 — Data profile implementation

Implement CSV loading and profiling.

Outputs:

```text
outputs/data_profile.json
outputs/data_preview.json
```

### PR 6 — Tool registry schemas

Create `packages/tool-registry` and define typed tool definitions.

No model integration yet.

### PR 7 — Mock agent loop

Create `packages/agent-core` with `MockProvider`.

The mock agent should write a simple pipeline deterministically so tests can run without API keys.

### PR 8 — OpenAI provider

Add `OpenAIProvider` behind the model interface. Do not leak API keys into logs or manifests.

### PR 9 — Result artifacts UI skeleton

Add workbench commands and panels with static render of artifacts from `gauntlet-sandbox/outputs`.

### PR 10 — Figure JSON IR

Create `packages/figure-model` and generate a simple editable figure spec from `visualization.py`.

---

## 19. Coding standards

The following rules apply across the whole codebase wherever possible. They are mandatory for project-specific Gauntlet code and should guide any patches made around upstream VS Code or Codex source.

### 19.1 Project-wide design principles

#### Style rules

- Write simple, readable code by default.
- Prefer explicit multi-line logic over compact one-liners.
- Avoid clever syntax, hidden side effects, and abstractions that save a few lines but reduce readability.
- Write code that looks like it was written and maintained by a careful human, not generated to minimize keystrokes.
- Use descriptive names for variables, functions, classes, and config fields.
- Keep functions focused on one job and keep modules small enough to navigate quickly.

#### Comment rules

- Add comments for non-obvious logic, assumptions, edge cases, and research-specific design decisions.
- Do not add filler comments that simply restate the code.
- Each module should start with a short docstring explaining its role in the research pipeline.
- Public functions and classes should have concise docstrings describing inputs, outputs, and side effects.
- Complex evaluation code, fold logic, visualization metrics, and latent-space scoring code must be commented clearly.

#### Anti-bloat rules

- Do not add unnecessary fallbacks, defensive branches, or assertion-heavy wrappers unless they protect a real failure mode.
- Do not create generic helper layers before there are at least two real call sites that need them.
- Do not hide core experiment logic behind large framework-like abstractions.
- Prefer a small number of explicit pipeline objects over many thin wrapper classes.

### 19.2 TypeScript

- strict TypeScript
- no `any` without justification
- Zod or JSON Schema validation at tool boundaries
- deterministic tests for tool schemas
- keep VS Code integration code separate from agent logic

### 19.3 Python

- Python 3.11+
- type hints
- pydantic for runtime schemas where useful
- no hidden global state
- generated code should call reusable helpers where possible
- output artifacts must be explicit

### 19.4 Rust

Codex internals may use Rust. Do not rewrite Rust components unless needed. Prefer adapter boundaries and generated documentation first.

### 19.5 Formatting

Add or preserve formatters:

```text
prettier / eslint for TypeScript
ruff / black for Python
cargo fmt / clippy for Rust where relevant
```

---

## 20. Testing strategy

### 20.1 Unit tests

Cover:

- tool schema validation
- sandbox manifest parsing
- allowed/denied file paths
- figure operation application
- code patch generation
- data profile generation

### 20.2 Integration tests

Cover:

- prompt file + CSV → pipeline run
- pipeline run → artifacts
- figure JSON → render
- figure operation → code patch → rerender

### 20.3 Golden tests

Create fixture datasets:

```text
tests/fixtures/tabular_classification/
tests/fixtures/tabular_regression/
tests/fixtures/time_series/
```

Each fixture should define:

```text
dataset.csv
prompt.md
expected_artifact_schema.json
expected_minimum_metrics.json
```

Do not require exact model scores for all tests. Require valid outputs and reasonable baseline behavior.

### 20.4 Agent tests

Agent tests should use:

- mock model provider for deterministic CI
- recorded tool-call transcripts for regression
- limited live provider tests behind an explicit environment flag

---

## 21. Observability and provenance

Every run should create a durable trace.

Minimum trace fields:

```json
{
  "run_id": "string",
  "created_at": "string",
  "prompt_file": "string",
  "prompt_hash": "string",
  "data_sources": [],
  "data_hashes": [],
  "pipeline_steps": [],
  "tool_calls": [],
  "files_created": [],
  "files_modified": [],
  "artifacts": [],
  "model_provider": "string",
  "model_name": "string",
  "policy": {},
  "status": "success | failed | partial",
  "errors": []
}
```

Run traces should support:

- reproducibility
- debugging
- audit
- rollback
- evaluation of agent quality

---

## 22. Configuration design

Create one project config and one run manifest.

### 22.1 Project config

```text
gauntlet.yaml
```

Human-editable. Defines desired behavior.

### 22.2 Run manifest

```text
outputs/run_manifest.json
```

Machine-written. Defines what happened.

Do not mix them.

---

## 23. Security checklist

Before any public release:

- [ ] no secrets committed
- [ ] generated files cannot write outside allowed output paths
- [ ] shell command execution denied by default
- [ ] network denied by default
- [ ] package installation gated by user approval
- [ ] model-generated code visibly attributed in run logs
- [ ] all tool calls logged
- [ ] data path traversal blocked
- [ ] large file and memory limits enforced
- [ ] run cancellation works
- [ ] output artifact size limits enforced
- [ ] dependency license review completed
- [ ] upstream licenses preserved

---

## 24. UX checklist

MVP screens:

- [ ] New Analysis
- [ ] Prompt input
- [ ] Dataset selection
- [ ] Data preview
- [ ] Plan preview
- [ ] Run progress
- [ ] Logs
- [ ] Results summary
- [ ] Metrics
- [ ] Figure gallery
- [ ] Figure editor
- [ ] Artifact browser
- [ ] Rerun button
- [ ] Export report button

UX states:

- [ ] no dataset selected
- [ ] invalid dataset
- [ ] unsupported file type
- [ ] agent planning
- [ ] code generation
- [ ] running
- [ ] failed run
- [ ] partial success
- [ ] completed run
- [ ] figure edited but not regenerated
- [ ] figure/code mismatch
- [ ] sandbox policy block

---

## 25. Open design questions

Resolve these through ADRs, not ad hoc code changes.

1. Should Gauntlet start as a VS Code extension, a Code OSS fork, or a standalone Electron app?
   - Default for MVP: extension-like integration first.

2. Should visualization code generate Matplotlib, Plotly, Vega-Lite, or a custom figure IR?
   - Default for MVP: custom figure IR plus Matplotlib/SVG export. Add Vega-Lite later if useful.

3. How much of Codex should be reused directly?
   - Default for MVP: learn from Codex, extract call graphs/action dictionaries, build adapters. Avoid direct deep coupling.

4. Should sandbox use Docker, local subprocess limits, or a language-level runner?
   - Default for MVP: local constrained runner first, Docker option later.

5. Should user see generated code by default?
   - Default: yes, but results panel should be primary. Generated code remains inspectable.

6. How will figure edits map to code?
   - Default: deterministic mappings for a small operation set. Use agent assistance only for unsupported edits.

7. What counts as MVP success?
   - Default: one tabular dataset can be loaded, profiled, modeled, evaluated, visualized, and figure-edited end to end.

---

## 26. Definition of MVP done

The MVP is done when all are true:

- user can create a new Gauntlet analysis
- user can provide prompt and CSV dataset
- agent can inspect data schema
- agent can generate or patch the six sandbox pipeline modules
- sandbox can run the modules in order
- outputs include data profile, analysis summary, model metrics, and at least one figure
- UI can show the outputs
- user can edit at least title and axis labels of a figure visually
- figure edit updates the figure JSON spec
- visualization code can be regenerated or patched from the edit
- rerun reproduces the edited figure
- all tool calls and generated files are logged
- generated code is constrained by sandbox policy
- repository has tests for the vertical slice

---

## 27. Coding-agent instruction block

Use this block as the starting instruction for coding agents.

```text
You are implementing Gauntlet, a safe agentic data-science IDE.

Read `program.md` first. Do not rewrite the entire VS Code or Codex source trees. Build a thin Gauntlet layer with explicit adapters.

Primary objective:
Create a working MVP vertical slice where a user prompt and CSV dataset produce sandboxed data loading, profiling, analysis, baseline training/evaluation, and editable figure artifacts.

Current priority:
1. Add project docs and scaffold.
2. Implement sandbox manifest and runner.
3. Implement deterministic placeholder pipeline.
4. Add data profiling.
5. Add tool registry schemas.
6. Add mock agent loop.
7. Add OpenAI provider only behind the provider interface.
8. Add result artifact UI panels.
9. Add figure JSON IR and basic edit operations.

Branch and push rules:
- Work on `early-prototype` for the early repo phase.
- Before editing, run `git branch --show-current`.
- If not already on `early-prototype`, run `git checkout early-prototype || git checkout -b early-prototype`.
- Push explicitly with `git push -u origin early-prototype`.
- Do not run `git push origin main`.
- Do not run a plain `git push` unless the upstream branch is confirmed to be `origin/early-prototype`.
- Feature branches are allowed, but they should branch from `early-prototype` and target `early-prototype` in pull requests.

Rules:
- Keep generated outputs out of git.
- Never commit secrets.
- Never allow model-generated code to run outside the sandbox.
- Network access is denied by default.
- Shell execution is denied by default.
- Preserve upstream license files and notices.
- Prefer adapters over invasive edits to `codex-main` and `vscode-main`.
- Every new subsystem needs tests.
- Every tool call needs a schema.
- Every run writes a manifest.
- Every figure edit must be reproducible through code or a figure spec.
- Write simple, readable code by default.
- Prefer explicit multi-line logic over compact one-liners.
- Avoid clever syntax, hidden side effects, and abstractions that reduce readability.
- Use descriptive names for variables, functions, classes, and config fields.
- Keep functions focused on one job.
- Keep modules small enough to navigate quickly.
- Add comments only for non-obvious logic, assumptions, edge cases, and research-specific design decisions.
- Start each module with a short docstring explaining its role in the research pipeline.
- Add concise docstrings to public functions and classes.
- Comment complex evaluation code, fold logic, visualization metrics, and latent-space scoring code clearly.
- Do not create generic helper layers before there are at least two real call sites that need them.
- Do not hide core experiment logic behind large framework-like abstractions.
- Prefer a small number of explicit pipeline objects over many thin wrapper classes.

Start with PR 1 from section 18.
```

---

## 28. Final project design coverage checklist

Use this to verify the project is not missing a major design area.

### Product

- [x] target user
- [x] product thesis
- [x] MVP scope
- [x] non-goals
- [x] user stories

### Engineering architecture

- [x] repo structure
- [x] branch strategy
- [x] workbench integration
- [x] agent architecture
- [x] model provider abstraction
- [x] tool registry
- [x] sandbox runner
- [x] data kernel
- [x] figure editor
- [x] Figma pipeline
- [x] observability

### Data science

- [x] loading
- [x] preprocessing
- [x] analysis
- [x] training
- [x] evaluation
- [x] visualization
- [x] reproducibility
- [x] artifact formats

### Safety

- [x] sandbox policy
- [x] path restrictions
- [x] network restrictions
- [x] dependency policy
- [x] shell policy
- [x] audit logs
- [x] secrets handling

### Development process

- [x] required `early-prototype` branch for early local development
- [x] explicit instruction not to push directly to `main`
- [x] first PR queue
- [x] testing plan
- [x] coding standards
- [x] CI expectations
- [x] ADRs
- [x] open questions

---

## 29. Suggested immediate next command sequence

For the first coding agent run:

```bash
git fetch origin
git checkout early-prototype || git checkout -b early-prototype
git branch --show-current
mkdir -p docs/architecture docs/decisions docs/milestones scripts tests/fixtures gauntlet-sandbox/outputs
touch gauntlet-sandbox/outputs/.gitkeep input_data/.gitkeep
git push -u origin early-prototype
```

Then implement PR 1 and PR 2 from section 18. Do not push directly to `main`.
