from bson.objectid import ObjectId  # noqa: N999
from sqlalchemy import delete, func
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
            query = await session.execute(select(DataChunk).where(DataChunk.chunk_id == chunk_id))
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
    
    async def delete_chunks_by_asset_id(self, asset_id: int):
        async with self.db_client() as session:
            query = delete(DataChunk).where(DataChunk.chunk_asset_id == asset_id)
            result = await session.execute(query)
            await session.commit()
        return result.rowcount

    async def get_chunk_ids_by_asset_id(self, asset_id: int) -> list[int]:
        async with self.db_client() as session:
            query = select(DataChunk.chunk_id).where(
                DataChunk.chunk_asset_id == asset_id
            )
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_chunk_count_by_asset_id(self, asset_id: int) -> int:
        async with self.db_client() as session:
            result = await session.execute(
                select(func.count(DataChunk.chunk_id)).where(
                    DataChunk.chunk_asset_id == asset_id
                )
            )

            return result.scalar_one()

    async def get_chunks_by_project_id(self, project_id: ObjectId, page_no: int=1, page_size: int=10):
        async with self.db_client() as session:
            
            query = (
                select(DataChunk)
                .where(DataChunk.chunk_project_id == project_id)
                .order_by(DataChunk.chunk_order)
                .offset((page_no - 1) * page_size)
                .limit(page_size)
            )
            
            result = await session.execute(query)
            records = result.scalars().all()
        return records

    async def get_total_chunks_count(self, project_id: ObjectId):
        record = 0
        async with self.db_client() as session:
            query = select(func.count(DataChunk.chunk_id)).where(DataChunk.chunk_project_id == project_id)
            result = await session.execute(query)
            record = result.scalar()
            
        return record 