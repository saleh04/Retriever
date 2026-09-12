import logging  # noqa: N999

from models.db_schemes import DataChunk, Project
from stores.llm.LLMEnums import DocumentTypeEnum

from .BaseController import BaseController


class NLPController(BaseController):

    def __init__(self, vectordb_client, generation_client, embedding_client, template_parser):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.vectordb_client = vectordb_client
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.template_parser = template_parser

    def create_collection_name(self, project_id: str):
        return f"collection_{self.vectordb_client.default_vector_size}_{project_id}".strip()

    async def reset_vector_db_collection(self, project: Project):
        collection_name = self.create_collection_name(project_id=str(project.project_id))
        return await self.vectordb_client.delete_collection(collection_name=collection_name)

    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=str(project.project_id))
        return await self.vectordb_client.get_collection_info(collection_name=collection_name)

    async def index_into_vector_db(self, project: Project, chunks: list[DataChunk],
                                   chunks_ids: list[int], do_reset: bool, batch_size: int = 64):

        collection_name = self.create_collection_name(project_id=str(project.project_id))

        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]
        
        _ = await self.vectordb_client.create_collection(collection_name=collection_name,
                                            embedding_size=self.embedding_client.embedding_size,
                                            do_reset=do_reset)

        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_metadata = metadata[i:i + batch_size]
            batch_record_ids = chunks_ids[i:i + batch_size]

            batch_vectors = self.embedding_client.embed_batch_texts(
                texts=batch_texts, 
                document_type=DocumentTypeEnum.DOCUMENT.value
            )

            if not batch_vectors:
                self.logger.error(f"Failed to embed batch from index {i} to {i + batch_size}")
                return False

            is_inserted = await self.vectordb_client.insert_many(
                collection_name=collection_name,
                texts=batch_texts,
                vectors=batch_vectors,
                metadata=batch_metadata,
                record_ids=batch_record_ids
            )
            
            if not is_inserted:
                self.logger.error(f"Failed to insert batch from index {i} to {i + batch_size}")
                return False

        return True

    async def search_in_vector_db(self, project: Project, query: str, limit: int = 5):

        collection_name = self.create_collection_name(project_id=str(project.project_id))

        vector = self.embedding_client.embed_text(text=query, document_type=DocumentTypeEnum.QUERY.value)

        if not vector or len(vector) == 0:
            return False

        search_results = await self.vectordb_client.search_by_vector(
            collection_name=collection_name,
            vector=vector,
            limit=limit
        )

        if not search_results:
            self.logger.error(f"Failed to search in vector DB for query: {query}")
            return False

        return search_results

    async def answer_rag_question(self, project: Project, query: str, limit: int = 5):

        answer, full_prompt, chat_history = None, None, None

        retrieved_docs = await self.search_in_vector_db(project=project, query=query, limit=limit)

        if not retrieved_docs or len(retrieved_docs) == 0:
            self.logger.error(f"No documents retrieved for query: {query}")
            return answer, full_prompt, chat_history
        
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                "doc_no": idx + 1,
                "chunk_text": self.generation_client.process_text(doc.text)
            })
            for idx, doc in enumerate(retrieved_docs)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {"query": query})

        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enum.SYSTEM.value
            )
        ]

        full_prompt = f"{documents_prompts}\n\n{footer_prompt}"

        answer = self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=chat_history
        )

        return answer, full_prompt, chat_history