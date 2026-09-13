from pydantic import BaseModel, Field, model_validator


class ProcessRequest(BaseModel):
    file_id: int | str | None = None
    chunk_size: int | None = Field(default=1000, ge=100, le=4000, description="Chunk size in characters")
    overlap: int | None = Field(default=100, ge=0, le=500, description="Overlap between chunks in characters")
    do_reset: bool = False
    
    @model_validator(mode="after")
    def overlap_validator(self) -> "ProcessRequest":
        chunk_size = self.chunk_size or 1000
        overlap = self.overlap or 0
        if overlap > chunk_size:
            raise ValueError(
                f"Overlap ({overlap}) cannot be greater than chunk size ({chunk_size})"
            )
          
        return self