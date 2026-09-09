from bson.objectid import ObjectId  # noqa: N999
from sqlalchemy import delete
from sqlalchemy.future import select

from .BaseDataModel import BaseDataModel
from .db_schemes import DataChunk


class chunkModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        return instance

    async def create_chunk(self, chunk: DataChunk):

        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
            await session.commit()
            await session.refresh(chunk)
        return chunk

    async def get_chunk(self, chunk_id:str):
        async with self.db_client() as session:
            query = await session.execute(select().where(DataChunk.chunk_id == chunk_id))
            chunk = query.scalar_one_or_none()
        return chunk

    async def insert_many_chunks(self, chunks:list, batch_size: int=100):

        async with self.db_client() as session:
            async with session.begin():        
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i+batch_size]
                    session.add_all(batch)
            await session.commit()
        return len(chunks)
    
    async def delete_chunks_by_project_id(self, project_id: ObjectId):
        async with self.db_client() as session:
            query = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(query)
            await session.commit()
        return result.rowcount

    async def get_chunks_by_project_id(self, project_id: ObjectId, page_no: int=1, page_size: int=10):
        async with self.db_client() as session:
            query = select(DataChunk).where(DataChunk.chunk_project_id == project_id).offset((page_no - 1) * page_size).limit(page_size)
            result = await session.execute(query)
            records = result.scalars().all()
        return records

    



