from __future__ import annotations

import os
from typing import TypeVar

from pydantic import BaseModel

from .config import get_saved_api_key
from .trace import RunTracer

ModelT = TypeVar("ModelT", bound=BaseModel)


class MissingAPIKey(RuntimeError):
    pass


class OpenAIStructuredClient:
    def __init__(self, model: str | None = None, tracer: RunTracer | None = None) -> None:
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1")
        self.tracer = tracer
        self.api_key = os.getenv("OPENAI_API_KEY") or get_saved_api_key()
        if not self.api_key:
            raise MissingAPIKey("OPENAI_API_KEY or a saved Applesauce API key is required unless --offline is used.")

    def parse(self, *, stage: str, system: str, user: str, output_model: type[ModelT]) -> ModelT:
        from openai import OpenAI

        if self.tracer:
            self.tracer.event(
                stage,
                "llm_request",
                model=self.model,
                output_model=output_model.__name__,
                system=system,
                user=user,
            )
        client = OpenAI(api_key=self.api_key)
        response = client.responses.parse(
            model=self.model,
            input=[
                {"role": "system", "content": f"{system}\n\nStage: {stage}"},
                {"role": "user", "content": user},
            ],
            text_format=output_model,
        )
        parsed = response.output_parsed
        if parsed is None:
            raise RuntimeError(f"OpenAI returned no parsed output for stage '{stage}'.")
        if self.tracer:
            self.tracer.event(stage, "llm_response", output=parsed)
        return parsed
