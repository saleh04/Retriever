import logging  # noqa: N999

from models.db_schemes import DataChunk, Project
from routes.schema.nlp import ChatMessage
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
                                   chunks_ids: list[int], do_reset: bool, batch_size: int = 40):

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

            batch_vectors = await self.embedding_client.embed_batch_texts(
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

    async def search_in_vector_db(self, project: Project, query: str, limit: int = 5, min_score: float = 0.0):

        collection_name = self.create_collection_name(project_id=str(project.project_id))

        vector = await self.embedding_client.embed_text(text=query, document_type=DocumentTypeEnum.QUERY.value)
        if vector is None or len(vector) == 0:
            self.logger.error(f"Failed to embed query: {query}")
            return None

        try:
            search_results = await self.vectordb_client.search_by_vector(
                collection_name=collection_name,
                vector=vector,
                limit=limit
            )
        except Exception as e:  # noqa: BLE001
            self.logger.error(f"VectorDB search failed: {e}")
            return None
        
        if search_results is None:
            return None
        
        if min_score > 0.0:
            search_results = [result for result in search_results if result.score >= min_score]
        
        return search_results

    async def answer_rag_question(self, project: Project, query: str, limit: int = 5,
                                  max_chars_per_doc: int = 3000, min_score: float = 0.3,
                                  chat_history: list[ChatMessage] | None = None):
        
        retrieved_docs = await self.search_in_vector_db(project=project, query=query, limit=limit, min_score=min_score)

        # Vector search failed due to error
        if retrieved_docs is None:
            return None, None, None
        
        # No matching documents found -> return graceful answer without burning LLM tokens
        if len(retrieved_docs) == 0:
            fallback_answer = self.template_parser.get("rag", "fallback_answer")
            return fallback_answer, "", [] 
        
        system_prompt = self.template_parser.get("rag", "system_prompt")

        documents_prompts = "\n".join([
            self.template_parser.get("rag", "document_prompt", {
                "doc_no": idx + 1,
                "chunk_text": doc.text[:max_chars_per_doc].strip()
            })
            for idx, doc in enumerate(retrieved_docs)
        ])

        footer_prompt = self.template_parser.get("rag", "footer_prompt", {"query": query})

        messages = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role=self.generation_client.enum.SYSTEM.value
            )
        ]
        
        if chat_history:
            for turn in chat_history:
                messages.append(
                    self.generation_client.construct_prompt(
                        prompt=turn.content,
                        role=turn.role,
                    )
                )

        full_prompt = f"{documents_prompts}\n\n{footer_prompt}"

        answer = await self.generation_client.generate_text(
            prompt=full_prompt,
            chat_history=messages
        )

        return answer, full_prompt, chat_history