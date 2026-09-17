from abc import ABC, abstractmethod  # noqa: N999

from models.db_schemes import RetrievedDocument


class VectorDBInterface(ABC):

    @abstractmethod
    async def connect(self):
        pass

    @abstractmethod
    async def disconnect(self):
        pass

    @abstractmethod
    async def is_collection_existed(self, collection_name: str) -> bool:
        pass

    @abstractmethod
    async def list_all_collections(self) -> list:
        pass

    @abstractmethod
    async def get_collection_info(self, collection_name: str) -> dict | None:
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str):
        pass

    @abstractmethod
    async def delete_by_record_ids(self, collection_name: str, record_ids: list[int]) -> bool:
        pass

    @abstractmethod
    async def create_collection(self, collection_name:str,
                          embedding_size: int | None = None, do_reset: bool = False):
        pass

    @abstractmethod
    async def insert_one(self, collection_name: str, text: str, vector: list,
                   metadata: dict | None = None,
                   record_id: str | None = None):
        pass

    @abstractmethod
    async def insert_many(self, collection_name: str, texts: list, vectors: list,
                   metadata: list | None = None,
                   record_ids: list | None = None, batch_size: int = 50):
        pass

    @abstractmethod
    async def search_by_vector(self, collection_name: str, vector: list, limit: int) -> list[RetrievedDocument]:
        pass