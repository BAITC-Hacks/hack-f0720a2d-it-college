from datetime import datetime
from typing import Annotated, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    StrictBool,
    StringConstraints,
    model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, max_length=5000)]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
RequiredText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
]
Description = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=10000)
]
Readiness = Literal["draft", "working", "ready", "priority"]
CardField = Literal[
    "title", "context", "need", "users", "data", "constraints", "expected_result",
    "success_criteria", "contact", "interaction_format",
]


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class CardFields(Schema):
    title: ShortText = ""
    context: Text = ""
    need: Text = ""
    users: Text = ""
    data: Text = ""
    constraints: Text = ""
    expected_result: Text = ""
    success_criteria: Text = ""
    contact: Text = ""
    interaction_format: Text = ""


class TaskCreate(CardFields):
    description: Description
    topic: RequiredText = "Общее"


class TaskPatch(Schema):
    expected_version: int = Field(ge=1, strict=True)
    description: Description | None = None
    topic: RequiredText | None = None
    title: ShortText | None = None
    context: Text | None = None
    need: Text | None = None
    users: Text | None = None
    data: Text | None = None
    constraints: Text | None = None
    expected_result: Text | None = None
    success_criteria: Text | None = None
    contact: Text | None = None
    interaction_format: Text | None = None

    @model_validator(mode="after")
    def validate_patch(self) -> "TaskPatch":
        changed = self.model_fields_set - {"expected_version"}
        if not changed:
            raise ValueError("Укажите хотя бы одно изменяемое поле")
        if any(getattr(self, name) is None for name in changed):
            raise ValueError("Поле нельзя обнулить через null; используйте пустую строку")
        return self


class TaskRead(TaskCreate):
    id: str
    status: Literal["draft", "finalized"]
    version: int
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None
    score: int | None = None
    readiness: Readiness | None = None


class TaskPage(Schema):
    items: list[TaskRead]
    total: int
    limit: int
    offset: int


class FinalizeRequest(Schema):
    confirmed: StrictBool
    expected_version: int = Field(ge=1, strict=True)

    @model_validator(mode="after")
    def require_confirmation(self) -> "FinalizeRequest":
        if not self.confirmed:
            raise ValueError("Финальная карточка должна быть подтверждена человеком")
        return self


class CriterionResult(Schema):
    key: str
    label: str
    points: int
    max_points: int
    missing_fields: list[CardField]
    explanation: str


class EvaluationRead(Schema):
    id: str
    task_id: str
    task_version: int
    score: int
    readiness: Readiness
    criteria: list[CriterionResult]
    missing_fields: list[CardField]
    card_snapshot: TaskCreate
    formula_version: str
    created_at: datetime


class ProposalCreate(Schema):
    team_id: RequiredText
    team_name: RequiredText
    idea: Description
    plan: Description
    timeframe: RequiredText
    prototype_url: HttpUrl


class ProposalRead(ProposalCreate):
    id: str
    task_id: str
    status: Literal["pending", "accepted", "rejected"]
    business_comment: Text
    created_at: datetime
    decided_at: datetime | None


class ProposalDecision(Schema):
    status: Literal["accepted", "rejected"]
    business_comment: Text = ""


class ProposalPage(Schema):
    items: list[ProposalRead]
    total: int
    limit: int
    offset: int


class ClarificationAnswer(Schema):
    field: CardField
    answer: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ]


class AnalysisRequest(Schema):
    description: Description
    card: CardFields = Field(default_factory=CardFields)
    answers: list[ClarificationAnswer] = Field(default_factory=list, max_length=30)


class ClarifyingQuestion(Schema):
    field: CardField
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=5, max_length=1000)
    ]


class FieldEvidence(Schema):
    field: CardField
    quote: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=5000)
    ]


class AnalysisResult(Schema):
    summary: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    missing_fields: list[CardField] = Field(max_length=10)
    questions: list[ClarifyingQuestion] = Field(min_length=3, max_length=10)
    suggested_card: CardFields
    evidence: list[FieldEvidence] = Field(max_length=10)
    warnings: list[Text] = Field(max_length=20)


class AnalysisResponse(AnalysisResult):
    provider: Literal["mock", "openai"]
    is_mock: bool
