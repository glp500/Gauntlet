from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .config import DEFAULT_API_KEY, DEFAULT_BASE_URL, load_local_settings, save_local_settings
from .pipeline import LocalModelSettings, run_pipeline


InputFunc = Callable[[str], str]


def prompt_required(prompt: str, input_func: InputFunc = input) -> str:
    while True:
        value = input_func(prompt).strip()
        if value:
            return value
        print("Please enter a value.")


def prompt_default(prompt: str, default: str, input_func: InputFunc = input) -> str:
    value = input_func(f"{prompt} [{default}]: ").strip()
    return value or default


def default_output_dir(dataset_path: Path) -> Path:
    return Path("runs") / f"{dataset_path.stem}_run_it_yaself"


def prompt_local_settings(input_func: InputFunc = input) -> LocalModelSettings:
    saved = load_local_settings()
    base_url = prompt_default("Local model base URL", saved.base_url or DEFAULT_BASE_URL, input_func)
    model = prompt_default("Local model name", saved.model or "local-model", input_func)
    api_key = prompt_default("Local API key", saved.api_key or DEFAULT_API_KEY, input_func)
    save_local_settings(base_url=base_url, model=model, api_key=api_key)
    return LocalModelSettings(base_url=base_url, model=model, api_key=api_key)


def interactive_run_it_yaself(input_func: InputFunc = input):
    dataset_path = Path(prompt_required("Dataset path: ", input_func))
    spec = prompt_required("Specifications: ", input_func)
    output_dir = Path(prompt_default("Output directory", str(default_output_dir(dataset_path)), input_func))
    settings = prompt_local_settings(input_func)
    print()
    return run_pipeline(
        dataset_path=dataset_path,
        spec=spec,
        output_dir=output_dir,
        settings=settings,
    )
