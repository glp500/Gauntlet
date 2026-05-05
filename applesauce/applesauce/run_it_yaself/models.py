from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ..models import ChartSpec


class CandidateQuestion(BaseModel):
    id: str
    text: str
    priority: int = Field(ge=0, le=100, default=50)
    rationale: str


class CandidateChart(BaseModel):
    id: str
    title: str
    insight: str
    rationale: str
    heuristic_score: float = Field(default=0.0, ge=0.0)
    chart_spec: ChartSpec


class CandidateTheme(BaseModel):
    name: Literal["executive", "playful", "calm", "technical", "editorial"]
    rationale: str
    priority: int = Field(ge=0, le=100, default=50)


class OptionSelection(BaseModel):
    selected_ids: list[str] = Field(default_factory=list, max_length=6)
    abstain: bool = False
    confidence: Literal["low", "medium", "high"] = "medium"
    reason: str = ""


class ThemeSelection(BaseModel):
    selected_name: Literal["executive", "playful", "calm", "technical", "editorial"] | None = None
    abstain: bool = False
    confidence: Literal["low", "medium", "high"] = "medium"
    reason: str = ""


class TitlePolish(BaseModel):
    title: str | None = None
    abstain: bool = False
    reason: str = ""

    @field_validator("title")
    @classmethod
    def title_not_blank(cls, value: str | None) -> str | None:
        if value is None:
            return value
        cleaned = value.strip()
        return cleaned or None
