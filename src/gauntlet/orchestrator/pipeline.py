"""Coordinator-driven vertical-slice pipeline."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from gauntlet.config import Settings
from gauntlet.io.artifact_collector import collect_artifacts
from gauntlet.io.input_loader import InputManifest, load_input_manifest
from gauntlet.io.summary_writer import write_summary
from gauntlet.llm.base import LLMBackend, LLMBackendError, LLMResponse
from gauntlet.llm.llama_cpp_client import LlamaCppBackend
from gauntlet.llm.ollama_client import OllamaBackend
from gauntlet.llm.openai_client import OpenAIBackend
from gauntlet.logging.setup import configure_run_logging
from gauntlet.orchestrator.code_generator import (
    ALLOWED_GENERATED_FILES,
    build_bundle_contract_prompts,
    build_codegen_prompts,
    build_single_file_codegen_prompts,
    parse_bundle_contract,
    parse_generated_file,
    parse_generated_bundle,
)
from gauntlet.orchestrator.code_reviewer import (
    build_review_prompts,
    parse_review_response,
)
from gauntlet.orchestrator.prompt_refiner import build_refinement_prompts
from gauntlet.orchestrator.router import StepRouter
from gauntlet.run_context import RunContext
from gauntlet.sandbox.executor import execute_sandbox
from gauntlet.sandbox.executor import execute_semantic_smoke_check
from gauntlet.sandbox.file_policy import (
    collect_generated_bundle_violations,
    collect_runtime_contract_violations,
)
from gauntlet.sandbox.manager import prepare_sandbox


_REPAIR_REQUIREMENTS = [
    "Keep the four-file bundle shape exactly: data_loader.py, preprocessing.py, analysis.py, figures.py.",
    "Expose the exact public functions: load_data, preprocess, run_analysis, create_figures.",
    "Use only pandas, matplotlib, and the standard library.",
    "Do not add shell execution, network access, or writes outside the provided output directory.",
    "Minimize changes and keep compliant files stable across repair attempts.",
]
_REVIEW_ADVISORY_CATEGORIES = {"contract", "readability", "sandbox"}
_REVIEW_BLOCKING_CATEGORIES = {"dependency", "other"}
_LOCAL_BACKEND_NAMES = {"ollama", "llama_cpp"}


class PipelineFailure(RuntimeError):
    """Structured failure used to control retry behavior."""

    def __init__(
        self,
        *,
        stage: str,
        issues: list[str],
        retryable: bool,
        code_bundle: dict[str, str] | None = None,
        review_result: dict[str, Any] | None = None,
        execution_result: dict[str, Any] | None = None,
        semantic_validation_result: dict[str, Any] | None = None,
        validation_violations: list[dict[str, str]] | None = None,
    ) -> None:
        self.stage = stage
        self.issues = issues
        self.retryable = retryable
        self.code_bundle = code_bundle
        self.review_result = review_result
        self.execution_result = execution_result
        self.semantic_validation_result = semantic_validation_result
        self.validation_violations = validation_violations or []
        self.failure_reason = "; ".join(issues) if issues else stage
        super().__init__(self.failure_reason)


class NonRetryablePipelineError(PipelineFailure):
    """Failure that should stop the run immediately."""

    def __init__(self, *, stage: str, issues: list[str]) -> None:
        super().__init__(stage=stage, issues=issues, retryable=False)


class RetryableCodegenError(PipelineFailure):
    """Failure that can be repaired by another code generation attempt."""

    def __init__(
        self,
        *,
        stage: str,
        issues: list[str],
        code_bundle: dict[str, str] | None = None,
        review_result: dict[str, Any] | None = None,
        semantic_validation_result: dict[str, Any] | None = None,
        validation_violations: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(
            stage=stage,
            issues=issues,
            retryable=True,
            code_bundle=code_bundle,
            review_result=review_result,
            semantic_validation_result=semantic_validation_result,
            validation_violations=validation_violations,
        )


class RetryableExecutionError(PipelineFailure):
    """Sandbox execution failure that can inform a repair attempt."""

    def __init__(
        self,
        *,
        issues: list[str],
        code_bundle: dict[str, str],
        execution_result: dict[str, Any],
    ) -> None:
        super().__init__(
            stage="execution",
            issues=issues,
            retryable=True,
            code_bundle=code_bundle,
            execution_result=execution_result,
        )


@dataclass(slots=True)
class Pipeline:
    """Own one configured execution of the vertical-slice workflow."""

    settings: Settings
    openai_backend: LLMBackend
    ollama_backend: LLMBackend
    llama_cpp_backend: LLMBackend
    router: StepRouter = field(init=False)

    def __post_init__(self) -> None:
        self.router = StepRouter(
            settings=self.settings,
            openai_backend=self.openai_backend,
            ollama_backend=self.ollama_backend,
            llama_cpp_backend=self.llama_cpp_backend,
        )

    def run(self) -> dict[str, Any]:
        """Execute the full pipeline and return the summary payload."""
        context = RunContext.create(self.settings)
        pipeline_logger, execution_logger = configure_run_logging(context)

        pipeline_logger.info("Starting run %s", context.run_id)
        context.set_status("running")

        artifacts = {"results": [], "figures": []}
        summary: dict[str, Any] = {}

        try:
            manifest = self._load_manifest(context, pipeline_logger)
            analysis_brief = self._refine_prompt(context, manifest, pipeline_logger)
            artifacts = self._run_codegen_loop(
                context=context,
                analysis_brief=analysis_brief,
                pipeline_logger=pipeline_logger,
                execution_logger=execution_logger,
            )
            context.attach_value("artifacts", artifacts)
            context.set_status("completed")

            summary = self._build_summary(
                context=context,
                status="completed",
                artifacts=artifacts,
                failure_reason=None,
            )
        except Exception as exc:
            failure_reason = str(exc)
            pipeline_logger.exception("Run failed: %s", failure_reason)
            context.set_status("failed", failure_reason=failure_reason)

            summary = self._build_summary(
                context=context,
                status="failed",
                artifacts=artifacts,
                failure_reason=failure_reason,
            )
        finally:
            write_summary(context, summary)
            context.attach_value("summary_path", str(context.summary_path))

        return summary

    def _run_codegen_loop(
        self,
        *,
        context: RunContext,
        analysis_brief: str,
        pipeline_logger: logging.Logger,
        execution_logger: logging.Logger,
    ) -> dict[str, list[str]]:
        """Generate, review, and execute bundles until one succeeds or attempts run out."""
        prior_bundle: dict[str, str] | None = None
        repair_brief: dict[str, Any] | None = None
        max_attempts = self.settings.max_codegen_attempts
        last_failure: PipelineFailure | None = None

        for attempt_number in range(1, max_attempts + 1):
            code_bundle: dict[str, str] | None = None
            bundle_contract: dict[str, list[str]] | None = None

            try:
                code_bundle, bundle_contract = self._generate_code(
                    context=context,
                    analysis_brief=analysis_brief,
                    attempt_number=attempt_number,
                    prior_bundle=prior_bundle,
                    repair_brief=repair_brief,
                    logger=pipeline_logger,
                )
                self._validate_code_bundle(
                    context=context,
                    code_bundle=code_bundle,
                    attempt_number=attempt_number,
                )

                prepare_sandbox(
                    context,
                    self.settings,
                    code_bundle,
                    attempt_number=attempt_number,
                )
                self._run_semantic_smoke_check(
                    context=context,
                    code_bundle=code_bundle,
                    bundle_contract=bundle_contract,
                    attempt_number=attempt_number,
                    logger=execution_logger,
                )

                review_result = self._review_code(
                    context=context,
                    code_bundle=code_bundle,
                    bundle_contract=bundle_contract,
                    attempt_number=attempt_number,
                    logger=pipeline_logger,
                )
                if review_result["blocking_issues"]:
                    raise RetryableCodegenError(
                        stage="review",
                        issues=review_result["blocking_issues"],
                        code_bundle=code_bundle,
                        review_result=review_result,
                    )

                execution_result = execute_sandbox(
                    context=context,
                    timeout_seconds=self.settings.run_timeout_seconds,
                    logger=execution_logger,
                    attempt_number=attempt_number,
                )

                if execution_result["status"] != "completed":
                    raise RetryableExecutionError(
                        issues=_extract_execution_issues(execution_result),
                        code_bundle=code_bundle,
                        execution_result=execution_result,
                    )

                artifacts = collect_artifacts(context, self.settings)
                artifact_issues = _collect_missing_artifact_issues(artifacts)
                if artifact_issues:
                    raise RetryableExecutionError(
                        issues=artifact_issues,
                        code_bundle=code_bundle,
                        execution_result={
                            "status": "failed",
                            "failure_reason": "; ".join(artifact_issues),
                            "artifacts": artifacts,
                            "stderr": "",
                            "stdout": "",
                        },
                    )
                context.record_attempt(
                    attempt_number=attempt_number,
                    stage="execution",
                    status="completed",
                    retryable=False,
                    details={
                        "review_advisory_issues": review_result["advisory_issues"],
                        "produced_results": artifacts["results"],
                        "produced_figures": artifacts["figures"],
                    },
                )
                pipeline_logger.info("Attempt %s completed successfully", attempt_number)
                return artifacts
            except RetryableCodegenError as exc:
                last_failure = exc
                self._record_attempt_failure(context, attempt_number, exc)
                pipeline_logger.warning(
                    "Attempt %s failed during %s: %s",
                    attempt_number,
                    exc.stage,
                    exc.failure_reason,
                )
                if attempt_number >= max_attempts:
                    break

                prior_bundle = exc.code_bundle or code_bundle
                repair_brief = self._build_repair_brief(
                    next_attempt_number=attempt_number + 1,
                    failure=exc,
                    prior_bundle=prior_bundle,
                )
                self._write_repair_brief(context, attempt_number + 1, repair_brief)
            except RetryableExecutionError as exc:
                last_failure = exc
                self._record_attempt_failure(context, attempt_number, exc)
                pipeline_logger.warning(
                    "Attempt %s failed during execution: %s",
                    attempt_number,
                    exc.failure_reason,
                )
                if attempt_number >= max_attempts:
                    break

                prior_bundle = exc.code_bundle
                repair_brief = self._build_repair_brief(
                    next_attempt_number=attempt_number + 1,
                    failure=exc,
                    prior_bundle=prior_bundle,
                )
                self._write_repair_brief(context, attempt_number + 1, repair_brief)

        if last_failure is None:
            raise RuntimeError("Code generation loop exited without a result.")

        raise RuntimeError(
            f"Code generation failed after {max_attempts} attempts. Last error: {last_failure.failure_reason}"
        )

    def _load_manifest(
        self,
        context: RunContext,
        logger: logging.Logger,
    ) -> InputManifest:
        """Load input files and save the manifest into metadata."""
        manifest = load_input_manifest(self.settings)
        context.attach_value("input_manifest", manifest.to_dict())
        context.record_step(
            "load_input_manifest",
            status="completed",
            details={"dataset_count": len(manifest.datasets)},
        )
        logger.info("Loaded manifest with %s dataset(s)", len(manifest.datasets))
        return manifest

    def _refine_prompt(
        self,
        context: RunContext,
        manifest: InputManifest,
        logger: logging.Logger,
    ) -> str:
        """Generate the structured analysis brief."""
        system_prompt, user_prompt = build_refinement_prompts(manifest)
        backend = self.router.select_backend("refine_prompt")
        response = self._generate_backend_response(
            context=context,
            backend=backend,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            prompt_file_name="refinement_prompt.txt",
            response_file_name="refine_response.json",
            step_name="refine_prompt",
        )

        (context.prompts_dir / "refined_prompt.txt").write_text(
            response.content,
            encoding="utf-8",
        )
        logger.info("Refinement step completed with %s", response.model)
        return response.content

    def _generate_code(
        self,
        *,
        context: RunContext,
        analysis_brief: str,
        attempt_number: int,
        prior_bundle: dict[str, str] | None,
        repair_brief: dict[str, Any] | None,
        logger: logging.Logger,
    ) -> tuple[dict[str, str], dict[str, list[str]] | None]:
        """Generate one code bundle for the current attempt."""
        backend = self.router.select_backend("generate_code")
        if backend.backend_name in _LOCAL_BACKEND_NAMES:
            return self._generate_code_file_by_file(
                context=context,
                analysis_brief=analysis_brief,
                attempt_number=attempt_number,
                prior_bundle=prior_bundle,
                repair_brief=repair_brief,
                backend=backend,
                logger=logger,
            )

        system_prompt, user_prompt = build_codegen_prompts(
            analysis_brief,
            prior_bundle=prior_bundle,
            repair_brief=repair_brief,
        )
        prompt_name = f"codegen_attempt_{attempt_number:02d}.txt"
        response_name = f"codegen_attempt_{attempt_number:02d}.json"
        response = self._generate_backend_response(
            context=context,
            backend=backend,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
            prompt_file_name=prompt_name,
            response_file_name=response_name,
            step_name="generate_code",
            attempt_number=attempt_number,
            retry_stage="backend_request",
        )

        try:
            code_bundle = parse_generated_bundle(response.content)
        except ValueError as exc:
            raise RetryableCodegenError(
                stage="static_validation",
                issues=[str(exc)],
            ) from exc

        logger.info("Code generation attempt %s created %s files", attempt_number, len(code_bundle))
        return code_bundle, None

    def _generate_code_file_by_file(
        self,
        *,
        context: RunContext,
        analysis_brief: str,
        attempt_number: int,
        prior_bundle: dict[str, str] | None,
        repair_brief: dict[str, Any] | None,
        backend: LLMBackend,
        logger: logging.Logger,
    ) -> tuple[dict[str, str], dict[str, list[str]]]:
        """Generate one sandbox bundle through smaller per-file local requests."""
        bundle_contract = self._generate_bundle_contract(
            context=context,
            analysis_brief=analysis_brief,
            attempt_number=attempt_number,
            repair_brief=repair_brief,
            backend=backend,
        )
        code_bundle: dict[str, str] = {}
        file_responses: list[LLMResponse] = []

        for file_name in ALLOWED_GENERATED_FILES:
            system_prompt, user_prompt = build_single_file_codegen_prompts(
                analysis_brief,
                file_name=file_name,
                bundle_contract=bundle_contract,
                generated_so_far=code_bundle,
                prior_bundle=prior_bundle,
                repair_brief=repair_brief,
            )
            prompt_name = f"codegen_attempt_{attempt_number:02d}__{file_name}.txt"
            response_name = f"codegen_attempt_{attempt_number:02d}__{file_name}.json"
            response = self._generate_backend_response(
                context=context,
                backend=backend,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                prompt_file_name=prompt_name,
                response_file_name=response_name,
                step_name="generate_code",
                attempt_number=attempt_number,
                retry_stage="backend_request",
                code_bundle=code_bundle or None,
            )
            try:
                code_bundle[file_name] = parse_generated_file(response.content)
            except ValueError as exc:
                raise RetryableCodegenError(
                    stage="static_validation",
                    issues=[str(exc)],
                    code_bundle=code_bundle or None,
                ) from exc

            file_responses.append(response)

        summary_usage = _merge_usage(response.usage for response in file_responses)
        request_details = [response.request_details for response in file_responses if response.request_details]
        synthetic_response = LLMResponse(
            content="",
            model=file_responses[-1].model,
            backend=backend.backend_name,
            usage=summary_usage,
            raw_response={"generated_files": list(code_bundle.keys())},
            request_details={"file_requests": request_details},
        )
        self._record_model_step(
            context,
            "generate_code",
            synthetic_response,
            attempt_number=attempt_number,
            extra_details={"file_generation_count": len(code_bundle)},
        )
        logger.info(
            "Local code generation attempt %s created %s files with %s smaller requests",
            attempt_number,
            len(code_bundle),
            len(file_responses),
        )
        return code_bundle, bundle_contract

    def _generate_bundle_contract(
        self,
        *,
        context: RunContext,
        analysis_brief: str,
        attempt_number: int,
        repair_brief: dict[str, Any] | None,
        backend: LLMBackend,
    ) -> dict[str, list[str]]:
        """Generate one shared contract for local file-by-file bundle generation."""
        system_prompt, user_prompt = build_bundle_contract_prompts(
            analysis_brief,
            repair_brief=repair_brief,
        )
        prompt_name = f"bundle_contract_attempt_{attempt_number:02d}.txt"
        response_name = f"bundle_contract_attempt_{attempt_number:02d}.json"
        response = self._generate_backend_response(
            context=context,
            backend=backend,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
            prompt_file_name=prompt_name,
            response_file_name=response_name,
            step_name="plan_bundle_contract",
            attempt_number=attempt_number,
            retry_stage="backend_request",
        )

        try:
            bundle_contract = parse_bundle_contract(response.content)
        except ValueError as exc:
            raise RetryableCodegenError(
                stage="semantic_validation",
                issues=[str(exc)],
            ) from exc

        context.record_step(
            "plan_bundle_contract",
            status="completed",
            attempt_number=attempt_number,
            backend=response.backend,
            model=response.model,
            details={
                "usage": response.usage,
                "request_details": response.request_details,
                "bundle_contract": bundle_contract,
            },
        )
        return bundle_contract

    def _validate_code_bundle(
        self,
        *,
        context: RunContext,
        code_bundle: dict[str, str],
        attempt_number: int,
    ) -> None:
        """Run deterministic bundle checks before review or execution."""
        policy_violations = collect_generated_bundle_violations(code_bundle)
        contract_violations = collect_runtime_contract_violations(code_bundle)
        validation_violations = policy_violations + contract_violations

        if validation_violations:
            failure_reason = _format_validation_failure(validation_violations)
            context.record_step(
                "validate_code_bundle",
                status="failed",
                attempt_number=attempt_number,
                details={
                    "failure_reason": failure_reason,
                    "violations": validation_violations,
                },
            )
            raise RetryableCodegenError(
                stage="static_validation",
                issues=[failure_reason],
                code_bundle=code_bundle,
                validation_violations=validation_violations,
            )

        context.record_step(
            "validate_code_bundle",
            status="completed",
            attempt_number=attempt_number,
        )

    def _review_code(
        self,
        *,
        context: RunContext,
        code_bundle: dict[str, str],
        bundle_contract: dict[str, list[str]] | None,
        attempt_number: int,
        logger: logging.Logger,
    ) -> dict[str, Any]:
        """Run the LLM review pass and normalize its output into blocking/advisory issues."""
        system_prompt, user_prompt = build_review_prompts(code_bundle, bundle_contract)
        backend = self.router.select_backend("review_code")
        response_name = f"review_attempt_{attempt_number:02d}.json"
        response = self._generate_backend_response(
            context=context,
            backend=backend,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format="json",
            response_file_name=response_name,
            step_name="review_code",
            attempt_number=attempt_number,
            retry_stage="backend_request",
            code_bundle=code_bundle,
        )

        try:
            raw_review_result = parse_review_response(response.content)
        except ValueError as exc:
            logger.warning("Review response for attempt %s could not be parsed: %s", attempt_number, exc)
            raw_review_result = {
                "status": "approved",
                "summary": "Review response could not be parsed, so review is advisory-only for this attempt.",
                "issues": [
                    {
                        "category": "other",
                        "message": f"Unparseable review response: {exc}",
                        "blocking": False,
                    }
                ],
            }

        review_result = self._normalize_review_result(raw_review_result)
        context.record_step(
            "review_code",
            status="completed",
            attempt_number=attempt_number,
            details={
                "blocking_issue_count": len(review_result["blocking_issues"]),
                "advisory_issue_count": len(review_result["advisory_issues"]),
            },
        )
        logger.info(
            "Review attempt %s status=%s blocking=%s advisory=%s",
            attempt_number,
            raw_review_result["status"],
            len(review_result["blocking_issues"]),
            len(review_result["advisory_issues"]),
            )
        return review_result

    def _run_semantic_smoke_check(
        self,
        *,
        context: RunContext,
        code_bundle: dict[str, str],
        bundle_contract: dict[str, list[str]] | None,
        attempt_number: int,
        logger: logging.Logger,
    ) -> None:
        """Run deterministic semantic checks before LLM review."""
        result = execute_semantic_smoke_check(
            context=context,
            bundle_contract=bundle_contract,
            logger=logger,
            attempt_number=attempt_number,
        )

        if result["status"] == "completed":
            return

        issues = _extract_semantic_validation_issues(result)
        raise RetryableCodegenError(
            stage="semantic_validation",
            issues=issues,
            code_bundle=code_bundle,
            semantic_validation_result=result,
        )

    def _normalize_review_result(self, review_result: dict[str, Any]) -> dict[str, Any]:
        """Keep the reviewer advisory unless it flags a narrow class of concrete issues."""
        blocking_issues: list[str] = []
        advisory_issues: list[str] = []

        for issue in review_result["issues"]:
            category = str(issue["category"]).strip().lower()
            message = str(issue["message"]).strip()
            is_blocking = bool(issue["blocking"])

            if category in _REVIEW_ADVISORY_CATEGORIES or not is_blocking:
                advisory_issues.append(message)
                continue

            if category in _REVIEW_BLOCKING_CATEGORIES:
                blocking_issues.append(message)
                continue

            advisory_issues.append(message)

        return {
            "status": review_result["status"],
            "summary": review_result["summary"],
            "issues": review_result["issues"],
            "blocking_issues": blocking_issues,
            "advisory_issues": advisory_issues,
        }

    def _record_model_step(
        self,
        context: RunContext,
        step_name: str,
        response: LLMResponse,
        *,
        attempt_number: int | None = None,
        extra_details: dict[str, Any] | None = None,
    ) -> None:
        """Store one completed model step in run metadata."""
        details: dict[str, Any] = {"usage": response.usage}
        if response.request_details:
            details["request_details"] = response.request_details

        if extra_details:
            details.update(extra_details)

        context.record_step(
            step_name,
            status="completed",
            attempt_number=attempt_number,
            backend=response.backend,
            model=response.model,
            details=details,
        )

    def _generate_backend_response(
        self,
        *,
        context: RunContext,
        backend: LLMBackend,
        system_prompt: str,
        user_prompt: str,
        step_name: str,
        prompt_file_name: str | None = None,
        response_file_name: str,
        response_format: str | None = None,
        attempt_number: int | None = None,
        retry_stage: str | None = None,
        code_bundle: dict[str, str] | None = None,
    ) -> LLMResponse:
        """Call one backend, persist its artifacts, and normalize retryable failures."""
        if prompt_file_name is not None:
            (context.prompts_dir / prompt_file_name).write_text(
                f"SYSTEM:\n{system_prompt}\n\nUSER:\n{user_prompt}",
                encoding="utf-8",
            )

        try:
            response = backend.generate(
                system_prompt,
                user_prompt,
                response_format=response_format,
            )
        except LLMBackendError as exc:
            self._write_backend_error_payload(
                context=context,
                file_name=response_file_name,
                backend_name=exc.backend,
                model=exc.model,
                error_message=str(exc),
                raw_response=exc.raw_response,
                request_details=exc.request_details,
            )
            if retry_stage is not None and attempt_number is not None:
                raise RetryableCodegenError(
                    stage=retry_stage,
                    issues=[str(exc)],
                    code_bundle=code_bundle,
                ) from exc
            raise RuntimeError(str(exc)) from exc

        self._write_response_payload(context, response_file_name, response)

        completeness_issue = _detect_incomplete_response(response)
        if completeness_issue is not None:
            if retry_stage is not None and attempt_number is not None:
                raise RetryableCodegenError(
                    stage=retry_stage,
                    issues=[completeness_issue],
                    code_bundle=code_bundle,
                )
            raise RuntimeError(completeness_issue)

        if step_name not in {"generate_code", "plan_bundle_contract"} or backend.backend_name not in _LOCAL_BACKEND_NAMES:
            self._record_model_step(
                context,
                step_name,
                response,
                attempt_number=attempt_number,
            )

        return response

    def _write_response_payload(
        self,
        context: RunContext,
        file_name: str,
        response: LLMResponse,
    ) -> None:
        """Persist a normalized response artifact."""
        payload = {
            "content": response.content,
            "model": response.model,
            "backend": response.backend,
            "usage": response.usage,
            "raw_response": response.raw_response,
            "request_details": response.request_details,
        }
        (context.responses_dir / file_name).write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _write_backend_error_payload(
        self,
        *,
        context: RunContext,
        file_name: str,
        backend_name: str,
        model: str,
        error_message: str,
        raw_response: dict[str, Any],
        request_details: dict[str, Any],
    ) -> None:
        """Persist backend transport or parsing failures as response artifacts."""
        payload = {
            "backend": backend_name,
            "content": "",
            "error": error_message,
            "model": model,
            "raw_response": raw_response,
            "request_details": request_details,
            "usage": None,
        }
        (context.responses_dir / file_name).write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _record_attempt_failure(
        self,
        context: RunContext,
        attempt_number: int,
        failure: PipelineFailure,
    ) -> None:
        """Persist one failed attempt to metadata."""
        context.record_attempt(
            attempt_number=attempt_number,
            stage=failure.stage,
            status="failed",
            retryable=failure.retryable,
            failure_reason=failure.failure_reason,
        )

    def _build_repair_brief(
        self,
        *,
        next_attempt_number: int,
        failure: PipelineFailure,
        prior_bundle: dict[str, str] | None,
    ) -> dict[str, Any]:
        """Build the structured payload passed into the next repair attempt."""
        stderr_summary = None
        if failure.execution_result:
            stderr_summary = _summarize_stderr(str(failure.execution_result.get("stderr", "")))

        return {
            "attempt_number": next_attempt_number,
            "failure_stage": failure.stage,
            "issues": failure.issues,
            "file_issues": _group_violations_by_file(failure.validation_violations),
            "file_guidance": _merge_file_guidance(
                _build_file_guidance(failure.validation_violations),
                _build_semantic_guidance(failure.semantic_validation_result),
            ),
            "violation_details": failure.validation_violations,
            "semantic_validation_result": failure.semantic_validation_result,
            "stderr_summary": stderr_summary,
            "preserve_requirements": _REPAIR_REQUIREMENTS,
        }

    def _write_repair_brief(
        self,
        context: RunContext,
        next_attempt_number: int,
        repair_brief: dict[str, Any],
    ) -> None:
        """Persist the repair brief for the next attempt."""
        file_name = f"repair_brief_attempt_{next_attempt_number:02d}.json"
        (context.responses_dir / file_name).write_text(
            json.dumps(repair_brief, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _build_summary(
        self,
        *,
        context: RunContext,
        status: str,
        artifacts: dict[str, list[str]],
        failure_reason: str | None,
    ) -> dict[str, Any]:
        """Build the summary payload written at the end of each run."""
        summary = {
            "run_id": context.run_id,
            "status": status,
            "summary_path": str(context.summary_path),
            "results": artifacts["results"],
            "figures": artifacts["figures"],
            "failure_reason": failure_reason,
            "attempt_count": context.metadata.get("attempt_count", 0),
            "attempts": context.metadata.get("attempts", []),
            "steps": context.metadata.get("steps", []),
            "metadata_path": str(context.metadata_path),
        }
        return summary


def _summarize_stderr(stderr: str) -> str | None:
    """Return the most useful tail of stderr for repair prompting."""
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    if not lines:
        return None

    tail = lines[-3:]
    return " | ".join(tail)


def _extract_execution_issues(execution_result: dict[str, Any]) -> list[str]:
    """Convert sandbox stderr into concise repair guidance."""
    failure_reason = str(execution_result.get("failure_reason") or "")
    stderr = str(execution_result.get("stderr") or "")
    stderr_lower = stderr.lower()
    issues: list[str] = []

    if "timed out" in failure_reason.lower():
        issues.append("Sandbox execution timed out. Reduce complexity or remove blocking work.")

    if "importerror" in stderr_lower:
        issues.append("Generated bundle has an import error or missing required symbol.")

    if "keyerror" in stderr_lower:
        issues.append("Generated code referenced a missing key in the data dictionary or results dictionary.")

    if "missing expected columns" in stderr_lower or "unknown group column" in stderr_lower:
        issues.append("Generated code assumed input columns that were not available at runtime.")

    if "filenotfounderror" in stderr_lower:
        issues.append("Generated code expected an input file or path that did not exist in the sandbox.")

    if "typeerror" in stderr_lower:
        issues.append("Generated code returned or consumed an invalid runtime type.")

    stderr_summary = _summarize_stderr(stderr)
    if stderr_summary:
        issues.append(f"Sandbox stderr summary: {stderr_summary}")

    if not issues:
        issues.append(failure_reason or "Sandbox execution failed for an unknown reason.")

    return issues


def build_pipeline(
    settings: Settings,
    openai_backend: LLMBackend | None = None,
    ollama_backend: LLMBackend | None = None,
    llama_cpp_backend: LLMBackend | None = None,
) -> Pipeline:
    """Build a pipeline with default or injected backends."""
    return Pipeline(
        settings=settings,
        openai_backend=openai_backend or OpenAIBackend(settings),
        ollama_backend=ollama_backend or OllamaBackend(settings),
        llama_cpp_backend=llama_cpp_backend or LlamaCppBackend(settings),
    )


def _merge_usage(usage_entries: Any) -> dict[str, Any] | None:
    """Combine usage records from multiple smaller backend requests."""
    merged: dict[str, Any] = {}
    saw_usage = False

    for usage in usage_entries:
        if not usage:
            continue

        saw_usage = True
        for key, value in usage.items():
            if not isinstance(value, (int, float)):
                merged.setdefault(key, value)
                continue

            current_value = merged.get(key)
            if isinstance(current_value, (int, float)):
                merged[key] = current_value + value
            else:
                merged[key] = value

    if not saw_usage:
        return None

    return merged


def _detect_incomplete_response(response: LLMResponse) -> str | None:
    """Recognize local-server replies that completed transport but not generation."""
    if response.backend == "ollama":
        if response.raw_response.get("done") is False:
            return (
                "Ollama returned an incomplete response with done=false. "
                "The local model may be too slow or the server may be unstable."
            )
        return None

    if response.backend != "llama_cpp":
        return None

    choices = response.raw_response.get("choices")
    if not isinstance(choices, list) or not choices:
        return "llama.cpp returned no choices. The local server may be unstable."

    first_choice = choices[0]
    finish_reason = first_choice.get("finish_reason")
    if finish_reason in {None, "length"}:
        return (
            "llama.cpp returned an incomplete response before reaching a normal stop condition. "
            "The local model may be too slow or the server may be unstable."
        )

    return None


def _format_validation_failure(violations: list[dict[str, str]]) -> str:
    """Render structured validation findings into a stable failure string."""
    rendered = "; ".join(entry["message"] for entry in violations)
    return f"Generated bundle failed file policy checks: {rendered}"


def _group_violations_by_file(
    violations: list[dict[str, str]],
) -> dict[str, list[str]]:
    """Group validation findings by file for targeted repair prompts."""
    grouped: dict[str, list[str]] = {}
    for violation in violations:
        file_name = violation["file"]
        grouped.setdefault(file_name, []).append(violation["message"])
    return grouped


def _build_file_guidance(
    violations: list[dict[str, str]],
) -> dict[str, list[str]]:
    """Translate specific rules into file-focused repair instructions."""
    guidance: dict[str, list[str]] = {}
    for violation in violations:
        file_name = violation["file"]
        rule = violation["rule"]
        target = guidance.setdefault(file_name, [])

        if rule == "sibling_module_import":
            target.append(
                f"{file_name} must be self-contained and must not import sibling generated modules."
            )
            if file_name == "analysis.py":
                target.append(
                    "run_analysis is not the pipeline entrypoint. Rewrite analysis.py as a pure analysis step that consumes the provided data dictionary and returns results only."
                )
                target.append(
                    "The sandbox runtime already loaded and preprocessed the input before calling run_analysis, so remove any load_data, preprocess, create_figures, or sibling-module orchestration."
                )
        elif rule == "analysis_file_loading":
            target.append(
                "analysis.py must not load files. It must only work with the provided `data` dictionary."
            )
            target.append(
                "Remove file-path inputs and data-loading calls. The sandbox runtime passes preprocessed in-memory data into run_analysis."
            )
        elif rule == "analysis_file_path_reference":
            target.append(
                "analysis.py must not reference input file paths, CSV names, or filesystem locations."
            )
            target.append(
                "Use only the provided `data` argument inside run_analysis. Do not hard-code dataset names, directories, or CSV filenames."
            )
        elif rule == "figures_show_call":
            target.append(
                "figures.py must save plots to the provided output directory and return the saved paths."
            )
            target.append(
                "Replace interactive display calls with figure saves in output_dir, close each figure, and return a list of written file paths."
            )
        elif rule == "main_block":
            target.append(
                "Generated modules are imported by run_analysis.py, so remove any `if __name__ == \"__main__\"` block and keep the file import-safe."
            )

    for file_name, entries in guidance.items():
        guidance[file_name] = list(dict.fromkeys(entries))

    return guidance


def _build_semantic_guidance(
    semantic_validation_result: dict[str, Any] | None,
) -> dict[str, list[str]]:
    """Translate semantic smoke-check failures into file-scoped repair guidance."""
    if not semantic_validation_result:
        return {}

    guidance: dict[str, list[str]] = {}

    loaded_keys = semantic_validation_result.get("loaded_keys", [])
    processed_keys = semantic_validation_result.get("processed_keys", [])
    result_table_names = semantic_validation_result.get("result_table_names", [])
    result_value_types = semantic_validation_result.get("result_value_types", {})
    figure_file_names = semantic_validation_result.get("figure_file_names", [])
    failure_reason = str(semantic_validation_result.get("failure_reason") or "")
    raw_stderr = str(semantic_validation_result.get("raw_stderr") or "")
    traceback_text = str(semantic_validation_result.get("traceback") or "")
    diagnostic_text = " ".join(
        text for text in [failure_reason, raw_stderr, traceback_text] if text
    ).lower()

    if loaded_keys or "load_data" in failure_reason:
        guidance.setdefault("data_loader.py", []).append(
            "Keep load_data aligned with the shared contract keys and return the dataset dictionary expected by preprocess."
        )

    if processed_keys or "preprocess" in failure_reason:
        guidance.setdefault("preprocessing.py", []).append(
            "preprocess must preserve or intentionally transform dictionary keys in a way that still matches what run_analysis expects."
        )

    if result_table_names or "run_analysis" in failure_reason:
        guidance.setdefault("analysis.py", []).append(
            "run_analysis must consume the processed dictionary keys from preprocess and return only pandas DataFrames under the contracted result_table_names."
        )

    if result_value_types:
        non_frame_keys = [
            key
            for key, value_type in result_value_types.items()
            if value_type != "DataFrame"
        ]
        if non_frame_keys:
            guidance.setdefault("analysis.py", []).append(
                "Replace non-DataFrame analysis outputs with pandas DataFrames. Invalid keys: "
                + ", ".join(sorted(non_frame_keys))
                + "."
            )

    if not result_table_names and "result tables" in failure_reason.lower():
        guidance.setdefault("analysis.py", []).append(
            "run_analysis returned no result tables. Add at least one non-empty pandas DataFrame result."
        )

    if figure_file_names or "create_figures" in failure_reason:
        guidance.setdefault("figures.py", []).append(
            "create_figures must use the processed data and analysis results to save at least one PNG and return its path."
        )

    if not figure_file_names and "figure" in failure_reason.lower():
        guidance.setdefault("figures.py", []).append(
            "The current figure logic produced no PNG outputs. Align the expected input keys with preprocess and run_analysis, then save at least one figure."
        )

    if any(token in diagnostic_text for token in ("nameerror", "importerror", "modulenotfounderror")):
        target_file = _infer_semantic_failure_file(raw_stderr, traceback_text) or "preprocessing.py"
        guidance.setdefault(target_file, []).append(
            f"{target_file} failed during module import or top-level evaluation. Ensure every top-level reference is imported and keep the file import-safe."
        )
        guidance.setdefault(target_file, []).append(
            "Do not rely on function-local imports for names used in module-level annotations or other top-level code."
        )

    for file_name, entries in guidance.items():
        guidance[file_name] = list(dict.fromkeys(entries))

    return guidance


def _merge_file_guidance(*guidance_maps: dict[str, list[str]]) -> dict[str, list[str]]:
    """Combine multiple file-guidance maps without duplicating messages."""
    merged: dict[str, list[str]] = {}
    for guidance_map in guidance_maps:
        for file_name, entries in guidance_map.items():
            target = merged.setdefault(file_name, [])
            for entry in entries:
                if entry not in target:
                    target.append(entry)
    return merged


def _extract_semantic_validation_issues(
    result: dict[str, Any],
) -> list[str]:
    """Summarize semantic smoke-check failures into repairable issue strings."""
    issues: list[str] = []
    failure_reason = str(result.get("failure_reason") or "").strip()
    if failure_reason:
        issues.append(failure_reason)

    loaded_keys = result.get("loaded_keys", [])
    processed_keys = result.get("processed_keys", [])
    result_table_names = result.get("result_table_names", [])
    figure_file_names = result.get("figure_file_names", [])
    result_value_types = result.get("result_value_types", {})
    raw_stderr = str(result.get("raw_stderr") or "")

    if loaded_keys:
        issues.append(f"load_data returned keys: {loaded_keys}")
    if processed_keys:
        issues.append(f"preprocess returned keys: {processed_keys}")
    if result_table_names:
        issues.append(f"run_analysis returned result tables: {result_table_names}")
    if result_value_types:
        issues.append(f"run_analysis result value types: {result_value_types}")
    if figure_file_names:
        issues.append(f"create_figures returned figure files: {figure_file_names}")
    if raw_stderr:
        stderr_summary = _summarize_stderr(raw_stderr)
        if stderr_summary:
            issues.append(f"Semantic smoke stderr summary: {stderr_summary}")

    if not issues:
        issues.append("Semantic smoke check failed for an unknown reason.")
    return issues


def _infer_semantic_failure_file(raw_stderr: str, traceback_text: str) -> str | None:
    """Best-effort mapping from a semantic smoke traceback to one generated file."""
    combined_text = "\n".join(part for part in [raw_stderr, traceback_text] if part)
    for file_name in ALLOWED_GENERATED_FILES:
        if file_name in combined_text:
            return file_name
    return None


def _collect_missing_artifact_issues(
    artifacts: dict[str, list[str]],
) -> list[str]:
    """Return retryable issues when execution finished without required artifacts."""
    issues: list[str] = []
    if not artifacts["results"]:
        issues.append("Execution completed but produced no result tables.")
    if not artifacts["figures"]:
        issues.append("Execution completed but produced no figures.")
    return issues
