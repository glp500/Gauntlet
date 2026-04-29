# Proto-Gauntlet

Proto-Gauntlet is a local analysis sandbox that turns a task plus CSV inputs into a small generated Python bundle, runs that bundle in a per-run workspace, and saves artifacts for inspection.

## Conda Setup

Create the environment from the repo root:

```powershell
conda env create -f environment.yml
conda activate proto-gauntlet
```

This installs the current runtime and test dependencies from [requirements.txt](/c:/Users/xeleo/Documents/ML%20Projects/Proto-Gauntlet/requirements.txt:1).

## OpenAI Key

Set `OPENAI_API_KEY` as an environment variable instead of storing it in the repo:

```powershell
# Current terminal only
$env:OPENAI_API_KEY="your_key_here"
```

For a persistent user-scoped variable on Windows:

```powershell
setx OPENAI_API_KEY "your_key_here"
```

If you use `setx`, open a new terminal before running the project.

## Ollama Setup

The default local model profile is now `gemma4:e2b`.

If you want to run the prompt refinement and code generation steps through Ollama instead of OpenAI, set these variables in your terminal:

```powershell
$env:GENERATION_BACKEND="ollama"
$env:REVIEW_BACKEND="ollama"
$env:OLLAMA_BASE_URL="http://localhost:11434/api"
$env:OLLAMA_MODEL="gemma4:e2b"
$env:OLLAMA_MODEL="hf.co/mradermacher/AutoBM-Seed-Coder-8B-R-GGUF:Q4_K_M"
```

`REVIEW_BACKEND` can stay as `openai` if you only want to move generation to Ollama.

When `GENERATION_BACKEND="ollama"`, the pipeline does not require `OPENAI_API_KEY`.

To use the larger local model for one run, add:

```powershell
python start.py --large-local-model
```

## llama.cpp Setup

If you want to run the local steps through `llama-server` instead of Ollama, start the server first and then point the pipeline at it:

```powershell
llama-server.exe `
  -m "C:\Users\xeleo\.ollama\models\blobs\sha256-4e30e2665218745ef463f722c0bf86be0cab6ee676320f1cfadf91e989107448" `
  -c 4096 `
  --threads -1 `
  --n-gpu-layers -1
```

Then configure the pipeline:

```powershell
$env:GENERATION_BACKEND="llama_cpp"
$env:REVIEW_BACKEND="llama_cpp"
$env:LLAMA_CPP_BASE_URL="http://localhost:8080"
$env:LLAMA_CPP_MODEL_PATH="C:\Users\xeleo\.ollama\models\blobs\sha256-4e30e2665218745ef463f722c0bf86be0cab6ee676320f1cfadf91e989107448"
$env:LLAMA_CPP_CTX_SIZE="4096"
$env:LLAMA_CPP_N_GPU_LAYERS="-1"
$env:LLAMA_CPP_THREADS="-1"
$env:LLAMA_CPP_TIMEOUT_SECONDS="180"
```

`LLAMA_CPP_MMPROJ_PATH` is optional and only matters if you later run a multimodal Gemma 4 setup through `llama-server`.

If `LLAMA_CPP_MODEL_PATH` is not set, the pipeline will try to discover the underlying local GGUF blob from the selected Ollama model automatically. That is useful for reuse, but it does not launch the server for you.

For the larger local model, use this blob path with `llama-server`:

```powershell
C:\Users\xeleo\.ollama\models\blobs\sha256-7121486771cbfe218851513210c40b35dbdee93ab1ef43fe36283c883980f0df
```

On this 6 GB RTX 3060, `gemma4:26b` is still likely to stay mostly CPU-bound. If generation remains slow, switch to a smaller GGUF such as an E2B or E4B Gemma 4 quant that fits the GPU better.

## Run

1. Set either `OPENAI_API_KEY` for OpenAI runs, the Ollama variables above for Ollama runs, or the `llama.cpp` variables above for `llama-server` runs.
2. Activate the conda environment.
3. Run `python start.py`.

```powershell
python start.py
```

To force the larger local Gemma profile for one run:

```powershell
python start.py --large-local-model
```

To run tests:

```powershell
pytest -q
```

Inputs are read from:

- `inputs/input.txt`
- `inputs/data/*.csv`

Run artifacts are written under:

- `workspace_runs/<run_id>/`
- `outputs/latest/`
