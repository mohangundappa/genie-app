from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    dataset: str | None = None


class AskResponse(BaseModel):
    question: str
    sql_query: str
    columns: list[str]
    rows: list[dict]
    row_count: int
    chart_config: dict | None = None
    explanation: str
    error: str | None = None


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
