from pydantic import ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    APP_NAME: str
    APP_VERSION: str
    
    FILE_ALLOWED_TYPES: list
    FILE_ALLOWED_SIZES_MB: int
    FILE_DEFAULT_CHUNK_SIZE: int

    POSTGRES_USERNAME: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_MAIN_DATABASE: str

    PROVIDER_BACKEND_LITERAL: list 
    GENERATION_BACKEND: str
    EMBEDDING_BACKEND: str

    OPENAI_API_KEY: str | None = None
    OPENAI_API_URL: str | None = None
    COHERE_API_KEY: str | None = None

    GENERATION_MODEL_ID: str | None = None
    EMBEDDING_MODEL_ID: str | None = None
    EMBEDDING_MODEL_SIZE: int | None = None

    INPUT_DEFAULT_MAX_CHARACTERS: int 
    GENERATION_DEFAULT_MAX_TOKENS: int | None = None
    GENERATION_DEFAULT_TEMP: float | None = None

    VECTOR_DB_BACKEND_LITERAL: list | None = None
    VECTOR_DB_BACKEND: str
    VECTOR_DB_PATH: str
    VECTOR_DB_DISTANCE_METHOD_LITERAL: list | None = None
    VECTOR_DB_DISTANCE_METHOD: str | None = None
    VECTOR_DB_PGVC_INDEX_THRESHOLD: int | None = None
    

    PRIMARY_LANGUAGE: str
    DEFAULT_LANGUAGE: str


    model_config = SettingsConfigDict(env_file=".env")

    @field_validator("GENERATION_BACKEND", "EMBEDDING_BACKEND")
    @classmethod
    def validate_backend(cls, value: str, info: ValidationInfo) -> str:
        # قراءة القيمة مباشرة من القيم المحملة (info.data)
        allowed_backends = info.data.get("PROVIDER_BACKEND_LITERAL") or []
        if allowed_backends and value not in allowed_backends:
            raise ValueError(
                f"Unsupported backend: {value}. "
                f"Expected one of {allowed_backends}."
            )
        return value

    @field_validator("VECTOR_DB_BACKEND")
    @classmethod
    def validate_vector_db_backend(cls, value: str, info: ValidationInfo) -> str:
        allowed = info.data.get("VECTOR_DB_BACKEND_LITERAL") or []
        if allowed and value not in allowed:
            raise ValueError(
                f"Unsupported vector database backend: {value}. "
                f"Expected one of {allowed}."
            )
        return value

    @field_validator("VECTOR_DB_DISTANCE_METHOD")
    @classmethod
    def validate_vector_db_distance_method(cls, value: str, info: ValidationInfo) -> str:
        allowed = info.data.get("VECTOR_DB_DISTANCE_METHOD_LITERAL") or []
        if value is not None and allowed and value not in allowed:
            raise ValueError(
                f"Unsupported vector database distance method: {value}. "
                f"Expected one of {allowed}."
            )
        return value

    @field_validator("EMBEDDING_MODEL_SIZE")
    @classmethod
    def validate_embedding_model_size(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError(
                "Embedding model size must be greater than 0."
            )
        return value

    @field_validator("VECTOR_DB_PGVC_INDEX_THRESHOLD")
    @classmethod
    def validate_pgvc_index_threshold(cls, value: int | None) -> int | None:
        if value is not None and value <= 0:
            raise ValueError(
                "PGVC index threshold must be greater than 0."
            )
        return value

def get_settings():
    return Settings()