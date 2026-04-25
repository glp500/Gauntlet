"""Integration tests for the early Gauntlet sandbox runner."""

from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path


def load_runner_module() -> object:
    """Import the runner module from its filesystem path."""
    project_root = Path(__file__).resolve().parents[1]
    runner_path = project_root / "scripts" / "run_gauntlet_sandbox.py"
    spec = importlib.util.spec_from_file_location("gauntlet_runner", runner_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load the sandbox runner module.")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RunGauntletSandboxTests(unittest.TestCase):
    """Validate the real CSV runner and its core artifact contract."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.runner = load_runner_module()
        cls.config_path = cls.project_root / "gauntlet-sandbox" / "gauntlet.yaml"
        cls.outputs_dir = cls.project_root / "gauntlet-sandbox" / "outputs"

    def tearDown(self) -> None:
        for file_name in [
            "run_manifest.json",
            "data_profile.json",
            "data_preview.json",
            "preprocessing_report.json",
            "analysis_summary.md",
            "model_metrics.json",
            "report.md",
        ]:
            artifact_path = self.outputs_dir / file_name
            if artifact_path.exists():
                artifact_path.unlink()

        figures_dir = self.outputs_dir / "figures"
        if figures_dir.exists():
            for child_path in figures_dir.iterdir():
                if child_path.is_file():
                    child_path.unlink()

    def test_runner_smoke_creates_core_artifacts(self) -> None:
        """The checked-in config should produce the expected output set."""
        exit_code = self.runner.run_pipeline(self.config_path)

        self.assertEqual(exit_code, 0)
        self.assertTrue((self.outputs_dir / "run_manifest.json").exists())
        self.assertTrue((self.outputs_dir / "data_profile.json").exists())
        self.assertTrue((self.outputs_dir / "data_preview.json").exists())
        self.assertTrue((self.outputs_dir / "preprocessing_report.json").exists())
        self.assertTrue((self.outputs_dir / "analysis_summary.md").exists())
        self.assertTrue((self.outputs_dir / "model_metrics.json").exists())
        self.assertTrue((self.outputs_dir / "report.md").exists())
        self.assertTrue((self.outputs_dir / "figures" / "figure_001.png").exists())
        self.assertTrue((self.outputs_dir / "figures" / "figure_001.svg").exists())
        self.assertTrue((self.outputs_dir / "figures" / "figure_001.json").exists())
        self.assertTrue((self.outputs_dir / "figures" / "figure_001.py").exists())

        profile = self._read_json(self.outputs_dir / "data_profile.json")
        self.assertEqual(profile["dataset"]["row_count"], 1200)
        self.assertEqual(profile["dataset"]["column_count"], 13)
        self.assertIn("age", profile["numeric_columns"])
        self.assertIn("gender", profile["categorical_columns"])
        self.assertEqual(len(profile["preview_rows"]), 5)

        model_metrics = self._read_json(self.outputs_dir / "model_metrics.json")
        self.assertEqual(model_metrics["train"]["status"], "completed")
        self.assertEqual(model_metrics["evaluation"]["status"], "completed")
        self.assertEqual(model_metrics["visualization"]["figure_count"], 1)
        self.assertGreater(model_metrics["evaluation"]["metrics"]["accuracy"], 0.0)

    def test_manifest_records_paths_and_step_order(self) -> None:
        """The run manifest should capture configured paths and execution order."""
        exit_code = self.runner.run_pipeline(self.config_path)

        self.assertEqual(exit_code, 0)
        manifest = self._read_json(self.outputs_dir / "run_manifest.json")

        self.assertEqual(manifest["status"], "success")
        self.assertTrue(manifest["prompt_file"].endswith("input\\raw_input.txt"))
        self.assertTrue(
            manifest["dataset_path"].endswith("input_data\\Teen_Mental_Health_Dataset.csv")
        )
        self.assertIn("prompt_hash", manifest)
        self.assertIn("dataset_hash", manifest)
        self.assertEqual(
            [step["name"] for step in manifest["pipeline_steps"]],
            [
                "data_loader",
                "data_preprocessing",
                "analysis",
                "train",
                "eval",
                "visualization",
            ],
        )
        figure_artifact_names = {artifact["name"] for artifact in manifest["artifacts"]}
        self.assertIn("figure_001", figure_artifact_names)
        self.assertIn("figure_001_svg", figure_artifact_names)

    def test_missing_dataset_path_fails_clearly(self) -> None:
        """The runner should fail on a missing configured dataset path."""
        with tempfile.TemporaryDirectory() as temp_dir_name:
            temp_dir = Path(temp_dir_name)
            sandbox_dir = temp_dir / "gauntlet-sandbox"
            sandbox_dir.mkdir(parents=True)
            (sandbox_dir / "outputs").mkdir()

            for file_name in [
                "data_loader.py",
                "data_preprocessing.py",
                "analysis.py",
                "train.py",
                "eval.py",
                "visualization.py",
            ]:
                shutil.copy2(self.project_root / "gauntlet-sandbox" / file_name, sandbox_dir / file_name)

            input_dir = temp_dir / "input"
            input_dir.mkdir()
            (input_dir / "raw_input.txt").write_text("Temporary prompt", encoding="utf-8")

            missing_config = "\n".join(
                [
                    "project:",
                    "  name: gauntlet-demo",
                    "  task: auto",
                    "  created_by: gauntlet",
                    "",
                    "input:",
                    "  prompt_file: ../input/raw_input.txt",
                    "  run_config_file: ../input/run_config.yaml",
                    "  data:",
                    "    type: local_file",
                    "    path: ../input_data/missing.csv",
                    "",
                    "runtime:",
                    "  python: \"3.11\"",
                    "  allow_network: false",
                    "  max_runtime_seconds: 120",
                    "  max_memory_mb: 4096",
                    "  max_output_mb: 256",
                    "",
                    "pipeline:",
                    "  steps:",
                    "    - data_loader",
                    "    - data_preprocessing",
                    "    - analysis",
                    "    - train",
                    "    - eval",
                    "    - visualization",
                    "",
                    "modeling:",
                    "  baseline_only: true",
                    "  target_column: depression_label",
                    "  model_type: logistic_regression",
                    "  train_test_split: 0.2",
                    "  random_seed: 42",
                    "",
                    "figures:",
                    "  output_format:",
                    "    - svg",
                    "    - png",
                    "    - json",
                    "  editable: true",
                    "",
                ]
            )
            config_path = sandbox_dir / "gauntlet.yaml"
            config_path.write_text(missing_config, encoding="utf-8")

            exit_code = self.runner.run_pipeline(config_path)

            self.assertEqual(exit_code, 1)
            manifest = self._read_json(sandbox_dir / "outputs" / "run_manifest.json")
            self.assertEqual(manifest["status"], "failed")
            self.assertIn("Configured dataset file not found", manifest["errors"][0]["message"])

    @staticmethod
    def _read_json(path: Path) -> dict:
        """Load a JSON artifact from disk."""
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)


if __name__ == "__main__":
    unittest.main()
