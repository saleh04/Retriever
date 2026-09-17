# Retriever

Retriever is a FastAPI application that turns uploaded text and PDF files into a searchable knowledge base and uses retrieval-augmented generation (RAG) to answer questions about those files.

This project is an implementation of the RAG course by Abu Bakr Soliman, with an emphasis on a structured application rather than notebook-only examples. The course playlist is available [here](https://www.youtube.com/playlist?list=PLvLvlVqNQGHCUR2p0b8a0QpVjDUg50wQj).

## What the Project Does

From a user perspective, the application provides this workflow:

1. Upload a text or PDF document to a project.
2. Split the document into smaller text chunks.
3. Generate embeddings for those chunks.
4. Store the embeddings in a vector database.
5. Search for the chunks most relevant to a question.
6. Send the question and retrieved context to an LLM to generate an answer.

The application supports OpenAI and Cohere providers for generation and embeddings. It supports PostgreSQL with pgvector and local on-disk Qdrant for vector storage.

## Technical Overview

The main components are:

- **FastAPI routes**: expose the upload, processing, indexing, search, and answer endpoints.
- **Controllers**: validate files, load documents, split content, perform vector searches, and coordinate RAG answers.
- **PostgreSQL**: stores projects, uploaded asset metadata, and processed chunks.
- **Embedding provider**: converts text chunks and search queries into vectors using OpenAI or Cohere.
- **Vector database**: stores and searches vectors using pgvector or local Qdrant.
- **Generation provider**: creates final answers using OpenAI or Cohere and localized RAG templates.

Important directories:

```text
src/
	main.py                 FastAPI application and startup lifecycle
	routes/                 HTTP routes and request schemas
	controllers/            File, processing, and NLP orchestration
	models/                 Database models and Alembic migrations
	stores/llm/             OpenAI and Cohere integrations and templates
	stores/vectordb/        pgvector and Qdrant integrations
	helpers/                Application configuration
	assets/files/            Uploaded files, grouped by project
	assets/database/         Local Qdrant data
docker/
	docker-compose.yml      PostgreSQL with the pgvector extension
```

## Requirements

- Python 3.12 or later
- Docker Desktop or Docker Engine with Compose
- An OpenAI API key, a Cohere API key, or compatible configured providers
- Git, if cloning the repository

The default configuration uses PostgreSQL/pgvector, OpenAI for generation, and Cohere for embeddings. You can change these choices in `src/.env`.

## Installation

Run the following commands from the repository root.

### Option A: Miniconda

Install [Miniconda](https://www.anaconda.com/docs/getting-started/concepts/anaconda-or-miniconda#quick-command-line-install), then create and activate the environment:

```bash
conda create -n retriever python=3.12
conda activate retriever
```

### Option B: Python virtual environment

```bash
python -m venv .venv
```

Activate it on Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Activate it on macOS or Linux:

```bash
source .venv/bin/activate
```

### Install Python dependencies

```bash
python -m pip install -r src/requirements.txt
```

## Configuration

Copy the application environment template:

Windows PowerShell:

```powershell
Copy-Item src\.env.example src\.env
```

macOS or Linux:

```bash
cp src/.env.example src/.env
```

Edit `src/.env` before starting the application. At minimum, configure the database connection and the API key for the selected providers.

### Application settings

| Variable | Purpose | Example |
| --- | --- | --- |
| `APP_NAME` | Application name | `Retriever` |
| `APP_VERSION` | Application version | `0.1.0` |
| `FILE_ALLOWED_TYPES` | Accepted MIME types | `["text/plain", "application/pdf"]` |
| `FILE_ALLOWED_SIZES_MB` | Maximum upload size | `10` |
| `FILE_DEFAULT_CHUNK_SIZE` | Upload read-buffer size | `512000` |
| `INPUT_DEFAULT_MAX_CHARACTERS` | Maximum input size used by the app | `1024` |
| `PROVIDER_BACKEND_LITERAL` | Allowed generation/embedding backend names | `["OPENAI", "COHERE"]` |
| `PRIMARY_LANGUAGE` | Language for RAG templates | `en` |
| `DEFAULT_LANGUAGE` | Fallback template language | `en` |

### PostgreSQL settings

| Variable | Purpose | Typical local value |
| --- | --- | --- |
| `POSTGRES_USERNAME` | PostgreSQL user | `postgres` |
| `POSTGRES_PASSWORD` | PostgreSQL password | The value used by Docker Compose |
| `POSTGRES_HOST` | Database host | `localhost` |
| `POSTGRES_PORT` | Host port | `5433` |
| `POSTGRES_MAIN_DATABASE` | Database name | `postgres` |

The included Compose file maps PostgreSQL container port `5432` to host port `5433`. Its current template only sets `POSTGRES_PASSWORD`; use matching values in `src/.env`, or update the Compose file to define a custom user and database.

### LLM and embedding settings

| Variable | Purpose |
| --- | --- |
| `GENERATION_BACKEND` | Generation provider: `OPENAI` or `COHERE` |
| `EMBEDDING_BACKEND` | Embedding provider: `OPENAI` or `COHERE` |
| `OPENAI_API_KEY` | OpenAI credential |
| `OPENAI_API_URL` | Optional OpenAI-compatible API URL |
| `COHERE_API_KEY` | Cohere credential |
| `GENERATION_MODEL_ID` | Generation model identifier |
| `EMBEDDING_MODEL_ID` | Embedding model identifier |
| `EMBEDDING_MODEL_SIZE` | Embedding vector dimension required by the model |
| `GENERATION_DEFAULT_MAX_TOKENS` | Default answer token limit |
| `GENERATION_DEFAULT_TEMP` | Default generation temperature |

### Vector database settings

| Variable | Purpose |
| --- | --- |
| `VECTOR_DB_BACKEND` | `PGVECTOR` or `QDRANT` |
| `VECTOR_DB_PATH` | Local path used by Qdrant |
| `VECTOR_DB_DISTANCE_METHOD` | Vector distance method, such as `cosine` |
| `VECTOR_DB_PGVC_INDEX_THRESHOLD` | Optional pgvector index threshold |
| `VECTOR_DB_BACKEND_LITERAL` | Allowed backend list, normally `["PGVECTOR", "QDRANT"]` |

When using `QDRANT`, no separate Qdrant server is required. The application uses local storage under `src/assets/database`. When using `PGVECTOR`, PostgreSQL must be running and reachable.

## Start PostgreSQL with Docker

Copy the Docker environment templates used by the compose stack:

Windows PowerShell:

```powershell
Copy-Item docker\env\.env.example.postgres docker\env\.env.postgres
Copy-Item docker\env\.env.example.app docker\env\.env.app
```

macOS or Linux:

```bash
cp docker/env/.env.example.postgres docker/env/.env.postgres
cp docker/env/.env.example.app docker/env/.env.app
```

Set the database password in `docker/env/.env.postgres` and the app database settings in `docker/env/.env.app`, then start the service:

```bash
docker compose -f docker/docker-compose.yml up -d
```

Check the service status:

```bash
docker compose -f docker/docker-compose.yml ps
```

Stop the service when it is no longer needed:

```bash
docker compose -f docker/docker-compose.yml down
```

## Run Database Migrations

The migration configuration is in `src/models/db_schemes/Retriever`. This project uses an Alembic folder named `alembic`, and the configuration file at `src/models/db_schemes/Retriever/alembic.ini` points to that directory.

Before running migrations, make sure the `sqlalchemy.url` value in `src/models/db_schemes/Retriever/alembic.ini` matches the PostgreSQL credentials and database configured in `src/.env`.

From the migration directory, run:

```bash
cd src/models/db_schemes/Retriever
alembic upgrade head
```

The initial migration creates the `projects`, `assets`, and `chunks` tables. The actual Alembic directory in this repository is `src/models/db_schemes/Retriever/alembic`.

## Run the API

Start the server from `src`, so Python can resolve the application packages and `src/.env`:

```bash
cd src
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

The application is available at:

- Local development API base URL: `http://localhost:5000`
- Local development Swagger UI: `http://localhost:5000/docs`
- Local development Scalar API reference: `http://localhost:5000/scalar`
- Docker stack FastAPI service: `http://localhost:8000`
- Docker Nginx entry point: `http://localhost:80`

## API Workflow

All application routes use the `/api/v1` prefix. A project is created automatically the first time an endpoint references its numeric `project_id`.

### 1. Upload a file

```bash
curl -X POST http://localhost:5000/api/v1/data/upload/1 \
	-F "file=@document.pdf"
```

Accepted files are `text/plain` and `application/pdf`, with a default maximum size of 10 MB. The response contains the database asset ID and generated file name.

### 2. Process the file into chunks

```bash
curl -X POST http://localhost:5000/api/v1/data/process/1 \
	-H "Content-Type: application/json" \
	-d '{"file_id": 1, "chunk_size": 1000, "overlap": 100, "do_reset": false}'
```

`file_id` can be the numeric asset ID or generated file name. Omit it to process every file in the project. `chunk_size` must be between 100 and 4000, and `overlap` cannot be greater than the chunk size.

### 3. Push chunks into the vector index

```bash
curl -X POST http://localhost:5000/api/v1/nlp/index/push/1 \
	-H "Content-Type: application/json" \
	-d '{"do_reset": true}'
```

Set `do_reset` to `true` when rebuilding the project index from scratch.

### 4. Inspect the vector index

```bash
curl http://localhost:5000/api/v1/nlp/index/info/1
```

### 5. Search indexed content

```bash
curl -X POST http://localhost:5000/api/v1/nlp/index/search/1 \
	-H "Content-Type: application/json" \
	-d '{"query": "What is this document about?", "limit": 5, "min_score": 0.5}'
```

`limit` accepts values from 1 to 50. `min_score` must be between 0 and 1.

### 6. Generate a RAG answer

```bash
curl -X POST http://localhost:5000/api/v1/nlp/index/answer/1 \
	-H "Content-Type: application/json" \
	-d '{"query": "Summarize the main conclusion.", "limit": 5, "min_score": 0.3}'
```

The response contains the generated `answer`. Complete the upload, process, and index steps before requesting an answer.

## Troubleshooting

- **Settings validation fails:** confirm that `src/.env` exists and that all required settings have values, including PostgreSQL host, port, database, and provider model IDs.
- **The database cannot be reached:** confirm Docker is running, PostgreSQL is healthy, and the application uses host port `5433`, not container port `5432`.
- **Migration errors:** run the migration from `src/models/db_schemes/Retriever` and verify `alembic.ini` points to the existing `alembic` directory.
- **Provider errors:** confirm the selected backend name is exactly `OPENAI` or `COHERE`, the matching API key is set, and the model ID and embedding size match the provider model.
- **Search returns no results:** make sure the file was processed and then pushed to the vector index for the same project ID.
- **Import or `.env` errors:** launch Uvicorn from `src`, not from the repository root.

## Current Limitations

- The application does not currently provide authentication, authorization, rate limiting, or user management.
- Projects are implicitly created from project IDs; there is no dedicated project-management endpoint.

