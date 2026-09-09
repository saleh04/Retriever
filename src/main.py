from contextlib import asynccontextmanager

from fastapi import FastAPI
from scalar_fastapi import get_scalar_api_reference
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from helpers.config import Settings
from routes import base, data, nlp
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = Settings() # type: ignore

    #Postgres connection
    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    app.state.db_engine = create_async_engine(postgres_conn) 
    app.state.db_client = sessionmaker(
        app.state.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    # LLM and VectorDB clients
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(settings)

    # Generation
    app.state.generation_client = llm_provider_factory.create(settings.GENERATION_BACKEND) 
    app.state.generation_client.set_generation_model(model_id=settings.GENERATION_MODEL_ID) 

    # Embedding
    app.state.embedding_client = llm_provider_factory.create(settings.EMBEDDING_BACKEND) # type: ignore
    app.state.embedding_client.set_embedding_model(model_id=settings.EMBEDDING_MODEL_ID,
                                              embedding_size=settings.EMBEDDING_MODEL_SIZE)

    # VectorDB
    app.state.vectordb_client = vectordb_provider_factory.create(settings.VECTOR_DB_BACKEND)
    app.state.vectordb_client.connect()

    app.state.template_parser = TemplateParser(language=settings.PRIMARY_LANGUAGE,
                                            default_language=settings.DEFAULT_LANGUAGE)
    
    yield

    app.state.db_engine.dispose()
    app.state.vectordb_client.disconnect()


app = FastAPI(lifespan=lifespan)

@app.get("/scalar", include_in_schema=False)
def scalar_docs():
    return get_scalar_api_reference(
        openapi_url=app.openapi_url,
        title="Scalar API"
    )
                  
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)