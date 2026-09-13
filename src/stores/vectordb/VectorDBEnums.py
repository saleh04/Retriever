from enum import Enum  # noqa: N999


class VectorDBEnums(Enum):
    PGVECTOR = "PGVECTOR"
    QDRANT = "QDRANT"

class DistanceMethodEnums(Enum):
    COSINE = "cosine"
    DOT = "dot"

class PgVectorTableSchemeEnums(Enum):
    ID = "id"
    TEXT = "text"
    VECTOR = "vector"
    CHUNK_ID = "chunk_id"
    METADATA = "metadata"
    _PREFIX = "pgvector"

class PgVectorDistanceMethodEnums(Enum):
    COSINE = "vector_cosine_ops"
    DOT = "vector_ip_ops"

class PgvectorIndexTypeEnums(Enum):
    HNSW = "HNSW"
    ivfflat = "ivfflat"