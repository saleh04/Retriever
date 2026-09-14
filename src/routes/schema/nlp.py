from typing import Literal

from pydantic import BaseModel, Field


class PushRequest(BaseModel):
    do_reset: bool = Field(default=False, description="Reset the database before pushing data")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class SearchRequest(BaseModel):
    query: str
    limit: int = Field(default=5, ge=1, le=50, description="Maximum number of search results")
    min_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum score for search results")
    chat_history: list[ChatMessage] | None = None