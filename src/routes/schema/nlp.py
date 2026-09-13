from pydantic import BaseModel, Field


class PushRequest(BaseModel):
    do_reset: bool| None = None

class SearchRequest(BaseModel):
    query: str
    limit: int | None = Field(default=5, ge=1, le=50, description="Maximum number of search results")
    min_score: float | None = Field(default=0.5, ge=0.0, le=1.0, description="Minimum score for search results")
    chat_history: list[str] | None = None