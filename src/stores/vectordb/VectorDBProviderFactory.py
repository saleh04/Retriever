from sqlalchemy.orm import sessionmaker  # noqa: N999

from controllers.BaseController import BaseController
from helpers.config import Settings

from .providers import PgVectorDB, QdrantDB
from .VectorDBEnums import VectorDBEnums


class VectorDBProviderFactory:
    def __init__(self, config: Settings, db_client: sessionmaker | None = None):
        self.db_client = db_client
        self.config = config
        self.BaseController = BaseController()
        
    def create(self, provider: str):
        if provider == VectorDBEnums.QDRANT.value:
            qdrant_db_client = self.BaseController.get_database_path(db_name=self.config.VECTOR_DB_PATH)

            return QdrantDB(
                db_client=qdrant_db_client,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                index_threshold=self.config.VECTOR_DB_PGVC_INDEX_THRESHOLD
            )
            
        if provider == VectorDBEnums.PGVECTOR.value:
            pgvector_db_client = self.db_client
            
            return PgVectorDB(
                db_client=pgvector_db_client,
                default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                distance_method=self.config.VECTOR_DB_DISTANCE_METHOD,
                index_threshold=self.config.VECTOR_DB_PGVC_INDEX_THRESHOLD
            )

        raise ValueError(
            f"Unsupported vector database provider: {provider}. "
            f"Expected PGVECTOR or QDRANT."
        )