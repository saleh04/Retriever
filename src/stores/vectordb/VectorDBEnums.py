from enum import Enum  # noqa: N999


class VectorDBEnums(Enum):
    PGVECTOR = "PGVECTOR"
    QDRANT = "QDRANT"

class DistanceMethodEnums(Enum):
    COSINE = "cosine"
    DOT = "dot"

class PgVectorTableSchemeEnums(Enum):
    ID = "id"
    TEXT = "Text"
    VECTOR = "vector"
    CHUNK_ID = "chunk_id"
    METADATA = "metadata"
    _PREFEX = "pgvector"

class PgVectorDistanceMethodEnums(Enum):
    COSINE = "vector_cosine_ops"
    DOT = "vector_l2_ops"

class PgvectorIndexTypeEnums(Enum):
    HNSW = "HNSW"
    ivfflat = "ivfflat"