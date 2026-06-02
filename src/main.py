from fastapi import FastAPI
from routes import admin, base, data, nlp


from helpers.config import get_settings
from stores.llm.LLMProviderFactory import LLMProviderFactory
from stores.vectordb.VectorDBProviderFactory import VectorDBProviderFactory
from stores.llm.templates.template_parser import TemplateParser
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

app = FastAPI()


@app.on_event("startup")
async def startup_span():
    
    settings = get_settings()

    postgres_conn = f"postgresql+asyncpg://{settings.POSTGRES_USERNAME}:{settings.POSTGRES_PASSWORD}@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_MAIN_DATABASE}"
    # DB 
    app.db_engine = create_async_engine(postgres_conn)
    app.db_client = sessionmaker(
        app.db_engine, class_=AsyncSession, expire_on_commit=False
    )

    #Factories
    llm_provider_factory = LLMProviderFactory(settings)
    vectordb_provider_factory = VectorDBProviderFactory(settings, db_client=app.db_client)

    # LLM Clients 
    app.generation_client = llm_provider_factory.create(
        provider=settings.GENERATION_BACKEND
    )

    if app.generation_client:
        app.generation_client.set_generation_model(
            model_id=settings.GENERATION_MODEL_ID
        )

    app.embedding_client = llm_provider_factory.create(
        provider=settings.EMBEDDING_BACKEND
    )

    if app.embedding_client:
        app.embedding_client.set_embedding_model(
            model_id=settings.EMBEDDING_MODEL_ID,
            embedding_size=settings.EMBEDDING_MODEL_SIZE
        )

    #Vector DB 
    app.vectordb_client = vectordb_provider_factory.create(
        provider=settings.VECTOR_DB_BACKEND
    )

    if app.vectordb_client:
        await app.vectordb_client.connect()

    # Templates
    app.template_parser = TemplateParser(
        language=settings.PRIMARY_LANG,
        default_language=settings.DEFAULT_LANG,
    )


@app.on_event("shutdown")
async def shutdown_span():
    if hasattr(app, "mongo_conn"):
       app.db_engine.dispose() 

    if hasattr(app, "vectordb_client") and app.vectordb_client:
       await app.vectordb_client.disconnect()   



# Routers 
app.include_router(base.base_router)
app.include_router(data.data_router)
app.include_router(nlp.nlp_router)
app.include_router(admin.admin_router)
