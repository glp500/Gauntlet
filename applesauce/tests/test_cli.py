import io
from pathlib import Path
from unittest.mock import patch

from applesauce.cli import LOADING_FRAMES, LoadingAnimation, main


FIXTURE = Path(__file__).parent / "fixtures" / "mixed.csv"


def test_no_args_starts_interactive_cli(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("APPLESAUCE_RUN_HISTORY_DIR", str(tmp_path / "history"))
    answers = iter(
        [
            "1",
            str(FIXTURE),
            "Explore revenue by customer segment",
            str(tmp_path),
            "",
        ]
    )

    exit_code = main([], input_func=lambda prompt: next(answers))

    assert exit_code == 0
    assert (tmp_path / "exploration.ipynb").exists()
    assert (tmp_path / "manifest.json").exists()


def test_interactive_cli_uses_model_choice_when_api_mode_selected(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    answers = iter(
        [
            "1",
            str(FIXTURE),
            "Explore revenue by customer segment",
            str(tmp_path),
            "n",
            "sk-test-key",
            "2",
        ]
    )

    with patch.dict("os.environ", {"APPLESAUCE_CONFIG": str(config_path)}, clear=False), patch("applesauce.cli.run_pipeline") as run_pipeline:
        run_pipeline.return_value.notebook_path = str(tmp_path / "exploration.ipynb")
        exit_code = main([], input_func=lambda prompt: next(answers))

    assert exit_code == 0
    assert "sk-test-key" in config_path.read_text(encoding="utf-8")
    run_pipeline.assert_called_once()
    assert run_pipeline.call_args.kwargs["offline"] is False
    assert run_pipeline.call_args.kwargs["model"] == "gpt-5.4"


def test_interactive_cli_reuses_saved_api_key(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"openai_api_key": "sk-saved-key"}', encoding="utf-8")
    answers = iter(
        [
            "1",
            str(FIXTURE),
            "Explore revenue by customer segment",
            str(tmp_path),
            "n",
            "1",
        ]
    )

    with patch.dict("os.environ", {"APPLESAUCE_CONFIG": str(config_path)}, clear=False), patch("applesauce.cli.run_pipeline") as run_pipeline:
        run_pipeline.return_value.notebook_path = str(tmp_path / "exploration.ipynb")
        exit_code = main([], input_func=lambda prompt: next(answers))

    assert exit_code == 0
    run_pipeline.assert_called_once()
    assert run_pipeline.call_args.kwargs["model"] == "gpt-5.5"


class TTYBuffer(io.StringIO):
    def isatty(self) -> bool:
        return True


def test_loading_animation_renders_on_one_line() -> None:
    stream = TTYBuffer()
    animation = LoadingAnimation(stream=stream)
    animation._render(LOADING_FRAMES[1])

    output = stream.getvalue()
    assert output.startswith("\rIch, wenn der Beat dropt: ")
    assert "\n" not in output
    assert "( ͡o ͜ʖ ͡o)" in output
