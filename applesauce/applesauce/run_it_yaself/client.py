from __future__ import annotations

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..trace import RunTracer
from .prompts import SMALL_MODEL_SYSTEM_PROMPT, repair_prompt

ModelT = TypeVar("ModelT", bound=BaseModel)


class LocalModelError(RuntimeError):
    pass


class OpenAICompatibleLocalClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str,
        tracer: RunTracer | None = None,
        max_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key or "local-not-needed"
        self.tracer = tracer
        self.max_retries = max(max_retries, 1)

    def parse(self, *, stage: str, user: str, output_model: type[ModelT]) -> ModelT:
        from openai import OpenAI

        client = OpenAI(base_url=self.base_url, api_key=self.api_key)
        current_prompt = user + "\n\nRequired JSON schema: " + json.dumps(output_model.model_json_schema(), ensure_ascii=True)
        last_error: Exception | None = None
        previous_output = ""

        for attempt in range(1, self.max_retries + 1):
            if self.tracer:
                self.tracer.event(
                    stage,
                    "llm_request",
                    model=self.model,
                    base_url=self.base_url,
                    output_model=output_model.__name__,
                    attempt=attempt,
                    user=current_prompt,
                )
            response = client.chat.completions.create(
                model=self.model,
                temperature=0.1,
                messages=[
                    {"role": "system", "content": SMALL_MODEL_SYSTEM_PROMPT},
                    {"role": "user", "content": current_prompt},
                ],
            )
            text = response.choices[0].message.content or ""
            previous_output = text
            if self.tracer:
                self.tracer.event(stage, "llm_raw_response", attempt=attempt, output=text)
            try:
                parsed = output_model.model_validate_json(_extract_json(text))
                if self.tracer:
                    self.tracer.event(stage, "llm_response", attempt=attempt, output=parsed)
                return parsed
            except (ValidationError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                current_prompt = repair_prompt(
                    stage=stage,
                    schema=output_model.model_json_schema(),
                    previous_output=previous_output,
                    validation_error=str(exc),
                )
                if self.tracer:
                    self.tracer.event(stage, "llm_repair_requested", attempt=attempt, error=str(exc))

        raise LocalModelError(f"Local model could not produce valid JSON for stage '{stage}': {last_error}")


def _extract_json(text: str) -> str:
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("empty model response")
    if cleaned.startswith("```"):
        lines = [line for line in cleaned.splitlines() if not line.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    if cleaned.startswith("{") or cleaned.startswith("["):
        return cleaned

    starts = [index for index, character in enumerate(cleaned) if character in "[{"]
    for start in starts:
        snippet = cleaned[start:].strip()
        try:
            json.loads(snippet)
        except json.JSONDecodeError:
            continue
        return snippet
    raise ValueError("response did not contain valid JSON")
