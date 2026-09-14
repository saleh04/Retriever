import json  # noqa: N999
import logging

from sqlalchemy import bindparam
from sqlalchemy.sql import text as sql_text

from models.db_schemes import RetrievedDocument

from ..VectorDBEnums import (
    DistanceMethodEnums,
    PgVectorDistanceMethodEnums,
    PgvectorIndexTypeEnums,
    PgVectorTableSchemeEnums,
)
from ..VectorDBInterface import VectorDBInterface


class PgVectorDB(VectorDBInterface):

    def __init__(self, db_client, default_vector_size: int=786,
                 distance_method:str | None=None, index_threshold: int = 100):

        self.db_client = db_client
        self.default_vector_size = default_vector_size
        self.index_threshold = index_threshold
        
        if distance_method == DistanceMethodEnums.COSINE.value:
            distance_method = PgVectorDistanceMethodEnums.COSINE.value
        elif distance_method == DistanceMethodEnums.DOT.value:
            distance_method = PgVectorDistanceMethodEnums.DOT.value
        self.distance_method = distance_method
        
        self.pgvector_table_prefix = PgVectorTableSchemeEnums._PREFIX.value
        self.default_index_name = lambda collection_name: f"{collection_name}_vector_idx"

        self.logger = logging.getLogger("uvicorn")
    
    @property
    def distance_operator(self):
        if self.distance_method == PgVectorDistanceMethodEnums.COSINE.value:
            return "<=>"
        else:
            return "<#>"
        
    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text(
                    "CREATE EXTENSION IF NOT EXISTS vector"
                ))
            await session.commit()
                
    async def disconnect(self):
        pass
    
    async def is_collection_existed(self, collection_name: str) -> bool:
        
        async with self.db_client() as session, session.begin():
            list_tbl = sql_text("SELECT * FROM pg_tables WHERE tablename = :collection_name")
            results = await session.execute(list_tbl, {"collection_name":collection_name})
            record = results.scalar_one_or_none()
        return record is not None
    
    async def list_all_collections(self) -> list:
        async with self.db_client() as session, session.begin():
            list_tbl = sql_text("SELECT * FROM pg_tables WHERE tablename LIKE :prefix")
            results = await session.execute(list_tbl, {"prefix": self.pgvector_table_prefix})
            record = results.scalars().all()
        return record
    
    async def get_collection_info(self, collection_name: str) -> dict | None:
        async with self.db_client() as session, session.begin():
            
            if not await self.is_collection_existed(collection_name=collection_name):
                return None
            
            table_info_sql = sql_text('''
               SELECT schemaname, tablename, tableowner, tablespace, hasindexes
               FROM pg_tables
               WHERE tablename = :collection_name
            ''')
            count_sql = sql_text(f"SELECT COUNT(*) FROM {collection_name}")
            
            table_info = await session.execute(table_info_sql, {"collection_name":collection_name})
            record_count = await session.execute(count_sql)
            
            table_data = table_info.fetchone()
            if not table_data:
                return None
            
            return {
                "table_info" : {
                    "schemaname": table_data[0],
                    "tablename": table_data[1],
                    "tableowner": table_data[2],
                    "tablespace": table_data[3],
                    "hasindexes": table_data[4]
                },
                "record_count" : record_count.scalar_one()
            }              
    
    async def delete_collection(self, collection_name: str):
        
        async with self.db_client() as session, session.begin():
            self.logger.info(f"Deleting collection: {collection_name}")
            delete_sql = sql_text(f"DROP TABLE IF EXISTS {collection_name}")
            await session.execute(delete_sql)
            await session.commit()
            
        return True

    async def delete_by_record_ids(self, collection_name: str, record_ids: list[int]) -> bool:
        if not record_ids or not await self.is_collection_existed(collection_name):
            return True

        async with self.db_client() as session, session.begin():
            delete_sql = sql_text(
                f"DELETE FROM {collection_name} WHERE {PgVectorTableSchemeEnums.CHUNK_ID.value} IN "
                ":record_ids"
            ).bindparams(bindparam("record_ids", expanding=True))
            await session.execute(delete_sql, {"record_ids": record_ids})

        return True
    
    async def create_collection(self, collection_name:str,
                              embedding_size: int | None = None, do_reset: bool = False):
        
        if do_reset:
            _ = await self.delete_collection(collection_name=collection_name)
            
        if not await self.is_collection_existed(collection_name=collection_name):
            self.logger.info(f"Creating collection: {collection_name}")
            async with self.db_client() as session, session.begin():
                
                create_tbl = sql_text(
                    f'CREATE TABLE {collection_name} ('
                        f'{PgVectorTableSchemeEnums.ID.value} bigserial PRIMARY KEY,'
                        f'{PgVectorTableSchemeEnums.TEXT.value} text, '
                        f'{PgVectorTableSchemeEnums.VECTOR.value} vector({embedding_size}), '
                        f'{PgVectorTableSchemeEnums.METADATA.value} jsonb DEFAULT \'{{}}\', '
                        f'{PgVectorTableSchemeEnums.CHUNK_ID.value} integer UNIQUE, '
                        f'FOREIGN KEY ({PgVectorTableSchemeEnums.CHUNK_ID.value}) REFERENCES chunks(chunk_id) '
                    ')'
                )
                
                await session.execute(create_tbl)
                await session.commit()
                
            return True
        
        return False
    
    async def is_index_existed(self, collection_name: str) -> bool:
        
        index_name = self.default_index_name(collection_name)
        async with self.db_client() as session, session.begin():
            list_tbl = sql_text("""
                                SELECT 1 FROM pg_indexes
                                WHERE tablename = :collection_name
                                AND indexname = :index_name
                                """)
            results = await session.execute(list_tbl, {"collection_name":collection_name, "index_name":index_name})
            record = bool(results.scalar_one_or_none())
        return record
    
    async def create_index(self, collection_name: str, index_type: str = PgvectorIndexTypeEnums.HNSW.value) -> bool:
        
        is_index_existed = await self.is_index_existed(collection_name=collection_name)
        if is_index_existed:
            return False
        
        index_name = self.default_index_name(collection_name)
        
        async with self.db_client() as session, session.begin():
            
            count_sql = sql_text(f"SELECT COUNT(*) FROM {collection_name}")
            result = await session.execute(count_sql)
            record_count = result.scalar_one()
            
            if record_count < self.index_threshold:
                return False
            
            self.logger.info(f"Creating index {index_name} on {collection_name}")
            create_idx = sql_text(f"""
                                    CREATE INDEX {index_name} ON {collection_name} 
                                    USING {index_type} ({PgVectorTableSchemeEnums.VECTOR.value} {self.distance_method});
                                    """)
            await session.execute(create_idx)
            await session.commit()
            self.logger.info(f"Index {index_name} created on {collection_name}")
            return True
    
    async def reset_vector_index(self, collection_name: str, index_type: str = PgvectorIndexTypeEnums.HNSW.value) -> bool:
        
        is_index_existed = await self.is_index_existed(collection_name=collection_name)
        if not is_index_existed:
            return False
        
        index_name = self.default_index_name(collection_name)
        
        async with self.db_client() as session, session.begin():
            
            self.logger.info(f"Resetting index {index_name} on {collection_name}")
            reset_idx = sql_text(f"""
                                    DROP INDEX {index_name};
                                    CREATE INDEX {index_name} ON {collection_name} 
                                    USING {index_type} ({PgVectorTableSchemeEnums.VECTOR.value} {self.distance_method});
                                    """)
            await session.execute(reset_idx)
            await session.commit()
            self.logger.info(f"Index {index_name} reset on {collection_name}")
            
        return True
    
    async def insert_one(self, collection_name: str, text: str, vector: list,
                       metadata: dict | None = None,
                       record_id: str | None = None):
        
        if not await self.is_collection_existed(collection_name=collection_name):
            self.logger.error(f"Can not insert new record to non-existed collection: {collection_name}")
            return False
        
        if not record_id:
            self.logger.info(f"Can not insert new record without chunk_id: {collection_name}")
            return False
        
        async with self.db_client() as session, session.begin():
            
            insert_tbl = sql_text(
                f'INSERT INTO {collection_name} ('
                    f'{PgVectorTableSchemeEnums.TEXT.value}, '
                    f'{PgVectorTableSchemeEnums.VECTOR.value}, '
                    f'{PgVectorTableSchemeEnums.METADATA.value}, '
                    f'{PgVectorTableSchemeEnums.CHUNK_ID.value}'
                ') VALUES (:text, :vector, :metadata, :chunk_id)'
                f'ON CONFLICT ({PgVectorTableSchemeEnums.CHUNK_ID.value}) DO UPDATE SET '
                f'{PgVectorTableSchemeEnums.TEXT.value} = EXCLUDED.{PgVectorTableSchemeEnums.TEXT.value}, '
                f'{PgVectorTableSchemeEnums.VECTOR.value} = EXCLUDED.{PgVectorTableSchemeEnums.VECTOR.value}, '
                f'{PgVectorTableSchemeEnums.METADATA.value} = EXCLUDED.{PgVectorTableSchemeEnums.METADATA.value}'
            )
            
            metadata_json = json.dumps(metadata, ensure_ascii=False) if metadata is not None else "{}"
            await session.execute(
                insert_tbl,
                {
                    f"{PgVectorTableSchemeEnums.TEXT.value}" : text,
                    f"{PgVectorTableSchemeEnums.VECTOR.value}" : "[" + ",".join([str(x) for x in vector]) + "]",
                    f"{PgVectorTableSchemeEnums.METADATA.value}" : metadata_json,
                    f"{PgVectorTableSchemeEnums.CHUNK_ID.value}" : record_id
                }
            )
            await session.commit()
            
        await self.create_index(collection_name=collection_name)

            
        return True
    
    async def insert_many(self, collection_name: str, texts: list, vectors: list,
                       metadata: list | None = None,
                       record_ids: list | None = None, batch_size: int = 50):
        
        if not await self.is_collection_existed(collection_name=collection_name):
            self.logger.error(f"Can not insert new records to non-existed collection: {collection_name}")
            return []
        
        if record_ids is None:
            self.logger.error(f"Can not insert batch without chunk_ids: {collection_name}")
            return False
        
        if len(vectors) != len(record_ids):
            self.logger.error(f"Can not insert batch without chunk_ids: {collection_name}")
            return False
        
        if metadata is None:
            metadata = [None] * len(texts)
        
        if len(texts) != len(vectors) or len(texts) != len(record_ids):
            self.logger.error(
                f"Texts, vectors and record_ids must have the same length: {collection_name}"
            )
            return False
        
        async with self.db_client() as session, session.begin():
            for i in range(0, len(texts), batch_size):
                batch_texts = texts[i:i+batch_size]
                batch_vectors = vectors[i:i+batch_size]
                batch_metadata = metadata[i:i+batch_size]
                batch_record_ids = record_ids[i:i+batch_size]
                
                values = []
                for _text, _vector, _metadata, _record_id in zip(batch_texts, batch_vectors, batch_metadata, batch_record_ids):
                    
                    metadata_json = json.dumps(_metadata, ensure_ascii=False) if _metadata is not None else "{}"
                    values.append(
                        {
                            f"{PgVectorTableSchemeEnums.TEXT.value}" : _text,
                            f"{PgVectorTableSchemeEnums.VECTOR.value}" : "[" + ",".join([str(x) for x in _vector]) + "]",
                            f"{PgVectorTableSchemeEnums.METADATA.value}" : metadata_json,
                            f"{PgVectorTableSchemeEnums.CHUNK_ID.value}" : _record_id
                        }
                    )
                
                batch_insert_tbl = sql_text(f'INSERT INTO {collection_name} '
                                    f'({PgVectorTableSchemeEnums.TEXT.value}, '
                                    f'{PgVectorTableSchemeEnums.VECTOR.value}, '
                                    f'{PgVectorTableSchemeEnums.METADATA.value}, '
                                    f'{PgVectorTableSchemeEnums.CHUNK_ID.value}) '
                                    f'VALUES (:text, :vector, :metadata, :chunk_id)'
                                    f'ON CONFLICT ({PgVectorTableSchemeEnums.CHUNK_ID.value}) DO UPDATE SET '
                                    f'{PgVectorTableSchemeEnums.TEXT.value} = EXCLUDED.{PgVectorTableSchemeEnums.TEXT.value}, '
                                    f'{PgVectorTableSchemeEnums.VECTOR.value} = EXCLUDED.{PgVectorTableSchemeEnums.VECTOR.value}, '
                                    f'{PgVectorTableSchemeEnums.METADATA.value} = EXCLUDED.{PgVectorTableSchemeEnums.METADATA.value}'
                                    )
                    
                await session.execute(batch_insert_tbl, values)
                
        await self.create_index(collection_name=collection_name)
                
        return True
    
    async def search_by_vector(self, collection_name: str, vector: list, limit: int) -> list[RetrievedDocument]:
        
        if not await self.is_collection_existed(collection_name=collection_name):
            self.logger.error(f"Can not insert new records to non-existed collection: {collection_name}")
            return []
        
        vector_value = "[" + ",".join(str(x) for x in vector) + "]"
        async with self.db_client() as session, session.begin():
            
            op = self.distance_operator
            
            if op == "<=>":
                # Cosine Similarity = 1 - Cosine Distance
                score_formula = f"1 - ({PgVectorTableSchemeEnums.VECTOR.value} {op} :vector)"
            else:
                # L2 Distance / Score
                score_formula = f"({PgVectorTableSchemeEnums.VECTOR.value} {op} :vector) * -1"
            
            search_tbl = sql_text(
                f"SELECT {PgVectorTableSchemeEnums.TEXT.value} AS text, {score_formula} AS score "
                f"FROM {collection_name} "
                f"ORDER BY {PgVectorTableSchemeEnums.VECTOR.value} {op} :vector ASC "
                f"LIMIT :limit"
            )
            
            results = await session.execute(search_tbl, {"vector": vector_value, "limit": limit})
            records = results.fetchall()
            
            if not records:
                return []
            
            return [
                RetrievedDocument(
                    text=record.text,
                    score=record.score
                )
                    for record in records
            ]