from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    dataset: str | None = None
    session_id: str | None = None


class PipelineStageInfo(BaseModel):
    name: str
    status: str
    duration_ms: float
    output: dict = {}


class AskResponse(BaseModel):
    question: str
    sql_query: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    chart_config: dict | None = None
    explanation: str
    error: str | None = None
    # Compound AI pipeline additions
    pipeline_stages: list[PipelineStageInfo] = []
    total_duration_ms: float = 0.0
    result_summary: str = ""
    follow_ups: list[str] = []
    session_id: str | None = None
    is_trusted: bool = False
    needs_clarification: bool = False
    clarification: str | None = None
    intent: dict = {}
    query_id: str = ""


class FeedbackRequest(BaseModel):
    query_id: str
    question: str
    vote: str
    sql_query: str | None = None
    session_id: str | None = None
    comment: str | None = None


class InstructionRequest(BaseModel):
    instruction: str
    scope: str = "global"
    dataset_name: str | None = None
    priority: int = 0
    is_active: int = 1


class BenchmarkCaseRequest(BaseModel):
    question: str
    expected_sql: str
    expected_result_pattern: str | None = None
    dataset_name: str | None = None
    tags: str | None = None
    difficulty: str = "medium"


class DatasetInfo(BaseModel):
    name: str
    columns: list[dict]
    row_count: int


class SettingsUpdate(BaseModel):
    openai_api_key: str | None = None
    openai_model: str | None = None


class QueryHistoryItem(BaseModel):
    id: int
    question: str
    sql_query: str
    result_summary: str | None
    chart_config: str | None
    dataset_name: str | None
    created_at: str
