from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class AttackCategory(str, Enum):
    SOCIAL_ENGINEERING = "social_engineering"
    PROMPT_INJECTION = "prompt_injection"
    DOC_FORGERY = "doc_forgery"
    KYC_BYPASS = "kyc_bypass"
    MULTI_TURN = "multi_turn"
    OTHER = "other"


class PersonaAvatar(BaseModel):
    avatar_id: str | None = None
    voice_id: str | None = None


class Persona(BaseModel):
    name: str
    display_name: str
    attack_category: AttackCategory
    difficulty: int = Field(ge=1, le=5)
    preferred_llm: str = "nvidia/nemotron-3-ultra"
    system_prompt: str
    attack_strategy: str
    avatar: PersonaAvatar = Field(default_factory=PersonaAvatar)
    success_signals: list[str] = Field(default_factory=list)


class PlantedCorrespondence(BaseModel):
    """A note / email / memo the adversary has previously planted into the
    bank's CRM for this account. Returned to blue when it calls
    `fetch_customer_correspondence`. This is the indirect-injection
    vector: the adversarial payload arrives via a TOOL RESULT, not via the
    user channel."""

    kind: Literal["note", "email", "memo", "document"]
    date: str
    subject: str | None = None
    body: str

    @field_validator("date", mode="before")
    @classmethod
    def _coerce_date(cls, v: Any) -> str:
        if isinstance(v, (date, datetime)):
            return v.isoformat()
        return str(v)


class Scenario(BaseModel):
    """A concrete situation a persona walks into a fight with."""

    name: str
    description: str
    target_account_holder: str
    target_amount_usd: float | None = None
    initial_message: str
    notes: str | None = None
    planted_correspondence: list[PlantedCorrespondence] | None = None


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: Any
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class Utterance(BaseModel):
    speaker: Literal["red", "blue", "system"]
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    reasoning: str | None = None


class Transcript(BaseModel):
    fight_id: str
    persona_name: str
    scenario_name: str
    blue_model: str
    blue_mode: Literal["standard", "lenient", "naive", "external"] = "standard"
    red_model: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: datetime | None = None
    utterances: list[Utterance] = Field(default_factory=list)
    end_reason: str | None = None  # "escalated" | "max_turns" | "policy_breach" | "red_ended_call" | "abort"


class Verdict(BaseModel):
    winner: Literal["red", "blue", "draw"]
    attack_category: AttackCategory
    policy_breaches: list[str] = Field(default_factory=list)
    escalation_correct: bool | None = None
    blue_score: int = Field(ge=0, le=100)
    red_score: int = Field(ge=0, le=100)
    notes: str
    deterministic_findings: list[str] = Field(default_factory=list)
    judge_model: str
    judge_reasoning: str | None = None
