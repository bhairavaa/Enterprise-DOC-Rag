# Getting Started

Step-by-step guide to running Enterprise Document RAG locally. This covers the
Docker Compose path (recommended — everything runs with one command).

## Prerequisites

- Docker Desktop (with Compose v2)
- An API key from at least one LLM provider (OpenAI, Anthropic, Gemini, Groq,
  or OpenRouter) if you want real chat *answers*. Without one, everything
  except answer generation works — ingestion, search, citations, auth.

## 1. Configure environment

```bash
cp .env.example .env
```

Open `.env` and fill in at least one provider key, e.g.:

```
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Leave everything else at its default — ports are already remapped to avoid
colliding with other local services (see [Ports](#ports) below).

## 2. Start the stack

```bash
docker compose up --build
```

This builds and starts 7 containers: Postgres, Redis, Qdrant, Phoenix
(tracing), the API, a Celery worker, and the frontend. First build takes a
few minutes (downloading base images, installing dependencies, and the
backend pulling in a local embedding model if you're using
`EMBEDDING_PROVIDER=huggingface`). Wait for the `api` service to log
`Application startup complete` before continuing.

Leave this running in its own terminal; open a second terminal for the next
steps.

## 3. Apply database migrations

```bash
docker compose exec api alembic upgrade head
```

One-time step (and again after pulling changes that add new migrations).

## 4. Seed demo API keys

```bash
docker compose exec api python scripts/seed_api_keys.py
```

Prints two keys, one per demo tenant:

```
acme: edr_...
globex: edr_...
```

**Copy these now** — like a real key-issuance flow, the raw key is only
shown once and isn't recoverable afterward. If you lose it, just re-run the
script (it always creates fresh keys; old ones stay valid until revoked).

## 5. Ingest the sample documents

```bash
docker compose exec api python -m app.ingestion.runner /data/sample_docs
```

Ingests the bundled two-tenant sample corpus (mixed PDF/DOCX/PPTX under
`sample_docs/acme/` and `sample_docs/globex/`). You should see output like:

```
Ingested: 5 [...]
Deleted:  0 []
```

Re-running this command later only re-embeds files that actually changed
(incremental indexing) — safe to run again any time.

## 6. Open the app

Go to **http://localhost:8080**.

1. Click **Settings** in the nav, paste in the `acme` key from step 4, save.
2. Click **Documents** — you should see the 5 ingested files with their
   department/doc_type/status.
3. Click **Chat** and ask a question, e.g. *"What is the remote work
   policy?"*. Citations stream in first, followed by the answer (answer
   generation needs a real LLM key from step 1 — without one, the request
   will fail at the generation step, but citations/retrieval still work).
4. Use the filter sidebar to scope by department/doc_type before asking.
5. Switch to the `globex` key in Settings to see the other tenant's
   documents — the `acme` key can never see `globex`'s data or vice versa,
   even with no filters applied.

## 7. Upload your own document (optional)

From the Documents page, use the upload control to add a PDF/DOCX/PPTX.
Unlike the CLI runner, this goes through the async path: the file is saved,
a Celery task is queued, and the page polls until ingestion completes
(usually a few seconds, longer the first time if the embedding model still
needs to load into the worker's memory).

## 8. Shut down

```bash
docker compose down
```

Use `down` (not just `stop`) if you also want to free the named volumes
(`pgdata`, `qdrant_storage`, `upload_storage`) — otherwise `docker compose
stop` keeps your ingested data for next time and just stops the containers.

---

## Debug/inspection endpoints

- `GET /api/v1/health` — liveness check, no auth needed.
- `POST /api/v1/search` — retrieval only, no generation. Useful for
  inspecting exactly what the hybrid pipeline (dense + BM25 fusion,
  parent-child merge, rerank, compression) returns for a query before it
  ever reaches the LLM. Requires `X-API-Key`.
- **Phoenix UI** — http://localhost:6006 — trace tree per request (retrieval
  latency, nodes retrieved, prompt/completion tokens, cache hit/miss).

## Ports

| Service | Host port |
|---|---|
| Frontend | 8080 |
| API | 8010 |
| Postgres | 5435 |
| Redis | 6380 |
| Qdrant (REST / gRPC) | 6335 / 6336 |
| Phoenix | 6006 |

## Troubleshooting

- **Chat returns an error, but citations show up fine:** expected without a
  real `LLM_PROVIDER` API key — the retrieval half of the pipeline doesn't
  need one, generation does.
- **`RERANKER_ENABLED=true` crashes the worker/API on a memory-constrained
  machine:** set it back to `false` in `.env` and restart. The rest of the
  pipeline is unaffected; only the rerank step is skipped. See
  `KNOWN_ISSUES.md`.
- **Running the API/worker locally (outside Docker) is very slow:** make
  sure `.env`'s `DATABASE_URL`/`QDRANT_URL`/`REDIS_URL` use `127.0.0.1`, not
  `localhost` — see `KNOWN_ISSUES.md` #2 for why this matters on Windows.
- **Port already in use:** another local service is likely on one of the
  ports above; change the host-side port in `docker-compose.yml` (left side
  of the `"host:container"` mapping only — container-internal ports must
  stay as-is).

## Running tests

```bash
cd backend
./.venv/Scripts/pytest tests/unit -v          # fast, no external services
./.venv/Scripts/pytest tests/integration -v   # needs Postgres + Qdrant running
```

See the main [README](README.md) for local (non-Docker) development setup,
architecture details, and [KNOWN_ISSUES.md](KNOWN_ISSUES.md) for tracked
defects and tuning decisions.
