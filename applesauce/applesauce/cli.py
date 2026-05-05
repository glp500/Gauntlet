from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
import sys
import threading

from .config import config_path, get_saved_api_key, save_api_key
from .eval import run_eval
from .llm import MissingAPIKey
from .pipeline import run_pipeline
from .run_it_yaself.cli import interactive_run_it_yaself
from .run_it_yaself.pipeline import LocalModelSettings, run_pipeline as run_it_yaself_pipeline


InputFunc = Callable[[str], str]
LOADING_FRAMES = [
    "( ͡° ͜ʖ ͡°)",
    "( ͡o ͜ʖ ͡o)",
    "( ͡O ͜ʖ ͡O)",
]
MODEL_CHOICES = [
    ("gpt-5.5", "Big Model Go Vroooom"),
    ("gpt-5.4", "Slightly more reasonable"),
    ("gpt-4.1", "Lil Baby Man"),
    ("gpt-5.3-codex", "Expensive Nerd"),
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="applesauce", description="Run the Applesauce data science exploration harness.")
    subparsers = parser.add_subparsers(dest="command")

    run = subparsers.add_parser("run", help="Run the agent harness and generate a notebook.")
    run.add_argument("--data", required=True, type=Path, help="Path to the source dataset.")
    run.add_argument("--spec", required=True, help="Short natural-language analysis specification.")
    run.add_argument("--out", required=True, type=Path, help="Output directory for notebook and artifacts.")
    run.add_argument("--model", default=None, help="OpenAI model name. Defaults to OPENAI_MODEL or gpt-4.1.")
    run.add_argument("--offline", action="store_true", help="Use deterministic local planning instead of OpenAI calls.")

    eval_parser = subparsers.add_parser("eval", help="Run the local harness reliability eval suite.")
    eval_parser.add_argument("--out", default=Path("runs/evals"), type=Path, help="Output directory for eval runs and report.")
    eval_parser.add_argument("--include-large", action="store_true", help="Include a synthetic large-dataset stability eval.")

    local_run = subparsers.add_parser("run-it-yaself", help="Run the separate local-model harness mode.")
    local_run.add_argument("--data", required=True, type=Path, help="Path to the source dataset.")
    local_run.add_argument("--spec", required=True, help="Short natural-language analysis specification.")
    local_run.add_argument("--out", required=True, type=Path, help="Output directory for notebook and artifacts.")
    local_run.add_argument("--base-url", default="http://127.0.0.1:1234/v1", help="OpenAI-compatible local model endpoint.")
    local_run.add_argument("--model", required=True, help="Local model name exposed by the endpoint.")
    local_run.add_argument("--api-key", default="local-not-needed", help="API key for the local endpoint, if required.")
    return parser


def prompt_required(prompt: str, input_func: InputFunc = input) -> str:
    while True:
        value = input_func(prompt).strip()
        if value:
            return value
        print("Please enter a value.")


def prompt_default(prompt: str, default: str, input_func: InputFunc = input) -> str:
    value = input_func(f"{prompt} [{default}]: ").strip()
    return value or default


def prompt_yes_no(prompt: str, default: bool, input_func: InputFunc = input) -> bool:
    suffix = "Y/n" if default else "y/N"
    while True:
        value = input_func(f"{prompt} [{suffix}]: ").strip().lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Please answer yes or no.")


def prompt_model_choice(input_func: InputFunc = input) -> str:
    print("OpenAI model")
    for index, (model, description) in enumerate(MODEL_CHOICES, start=1):
        print(f"{index}. {model} - {description}")

    while True:
        value = prompt_default("Choose a model", "1", input_func)
        if value.isdigit():
            selected = int(value)
            if 1 <= selected <= len(MODEL_CHOICES):
                return MODEL_CHOICES[selected - 1][0]
        matching = [model for model, _ in MODEL_CHOICES if model == value]
        if matching:
            return matching[0]
        print("Please choose one of the listed model numbers.")


def ensure_api_key(input_func: InputFunc = input) -> None:
    if get_saved_api_key():
        print(f"Using saved OpenAI API key from {config_path()}.")
        return

    api_key = prompt_required("OpenAI API key: ", input_func)
    path = save_api_key(api_key)
    print(f"Saved OpenAI API key to {path}.")


def default_output_dir(dataset_path: Path) -> Path:
    return Path("runs") / dataset_path.stem


class LoadingAnimation:
    def __init__(self, interval: float = 0.5, stream = None) -> None:
        self.interval = interval
        self.stream = stream or sys.stdout
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_length = 0

    def _render(self, frame: str) -> None:
        line = f"Ich, wenn der Beat dropt: {frame}"
        padding = " " * max(0, self._last_length - len(line))
        self.stream.write(f"\r{line}{padding}")
        self.stream.flush()
        self._last_length = len(line)

    def _animate(self) -> None:
        frame_index = 0
        self._render(LOADING_FRAMES[frame_index])
        frame_index += 1
        while not self._stop.wait(self.interval):
            self._render(LOADING_FRAMES[frame_index % len(LOADING_FRAMES)])
            frame_index += 1

    def start(self) -> None:
        if not hasattr(self.stream, "isatty") or not self.stream.isatty():
            return
        self._thread = threading.Thread(target=self._animate, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join()
        self.stream.write("\r" + (" " * self._last_length) + "\r")
        self.stream.flush()


def run_pipeline_with_animation(run_callable=None, **kwargs):
    animation = LoadingAnimation()
    animation.start()
    try:
        if run_callable is not None:
            return run_callable()
        return run_pipeline(**kwargs)
    finally:
        animation.stop()


def interactive_main(input_func: InputFunc = input) -> int:
    print("Applesauce Data Science Harness")
    print("1. Create exploration notebook")
    print("2. Run it yaself mode")
    print("3. Exit")
    choice = prompt_default("Choose an option", "1", input_func)

    if choice == "3":
        print("No run started.")
        return 0
    if choice == "2":
        manifest = run_pipeline_with_animation(run_callable=lambda: interactive_run_it_yaself(input_func))
        print()
        print(f"Notebook written to: {manifest.notebook_path}")
        print(f"Manifest written to: {Path(manifest.notebook_path).parent / 'manifest.json'}")
        return 0
    if choice != "1":
        print(f"Unknown option: {choice}")
        return 2

    dataset_path = Path(prompt_required("Dataset path: ", input_func))
    spec = prompt_required("Specifications: ", input_func)
    output_dir = Path(prompt_default("Output directory", str(default_output_dir(dataset_path)), input_func))
    offline = prompt_yes_no("Run without OpenAI API calls", True, input_func)
    model = None
    if not offline:
        ensure_api_key(input_func)
        model = prompt_model_choice(input_func)
        print()

    try:
        manifest = run_pipeline_with_animation(
            dataset_path=dataset_path,
            spec=spec,
            output_dir=output_dir,
            offline=offline,
            model=model,
        )
    except MissingAPIKey as exc:
        print(f"Error: {exc}")
        return 2

    print()
    print(f"Notebook written to: {manifest.notebook_path}")
    print(f"Manifest written to: {output_dir / 'manifest.json'}")
    return 0


def main(argv: list[str] | None = None, input_func: InputFunc = input) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        return interactive_main(input_func)

    if args.command == "run":
        try:
            manifest = run_pipeline_with_animation(
                dataset_path=args.data,
                spec=args.spec,
                output_dir=args.out,
                offline=args.offline,
                model=args.model,
            )
        except MissingAPIKey as exc:
            parser.error(str(exc))
            return 2

        print(f"Notebook written to: {manifest.notebook_path}")
        print(f"Manifest written to: {args.out / 'manifest.json'}")
        return 0
    if args.command == "eval":
        report = run_eval(args.out, include_large=args.include_large)
        print(f"Eval report written to: {args.out / 'eval_report.json'}")
        print(f"Passed {report['passed']} of {report['total']} checks.")
        return 0
    if args.command == "run-it-yaself":
        manifest = run_pipeline_with_animation(
            run_callable=lambda: run_it_yaself_pipeline(
                dataset_path=args.data,
                spec=args.spec,
                output_dir=args.out,
                settings=LocalModelSettings(
                    base_url=args.base_url,
                    model=args.model,
                    api_key=args.api_key,
                ),
            )
        )
        print(f"Notebook written to: {manifest.notebook_path}")
        print(f"Manifest written to: {args.out / 'manifest.json'}")
        return 0
    parser.error("Unknown command.")
    return 2
