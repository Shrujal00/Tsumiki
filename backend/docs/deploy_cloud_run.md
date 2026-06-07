# Deploy the Tsumiki backend to Google Cloud Run

Concise path to a public HTTPS URL the Android app and Next.js dashboard call as
their backend base URL. Run all commands from the `backend/` directory.

> **Never put real secret values in this file, in git, or in `--set-env-vars`.**
> Use Secret Manager for anything sensitive (keys), plain env vars only for
> non-secret config.

## 0. One-time prerequisites

```bash
gcloud auth login
gcloud config set project YOUR_PROJECT_ID
gcloud services enable run.googleapis.com artifactregistry.googleapis.com \
    cloudbuild.googleapis.com secretmanager.googleapis.com
```

## 1. Environment variables (from Task 1's `config.py`)

`config.py` validates these on boot. Classify them:

**Secrets — store in Secret Manager, never as plain env vars:**

| Key                         | What it is                         |
|-----------------------------|------------------------------------|
| `LANGSMITH_API_KEY`         | LangSmith tracing key              |
| `OLLAMA_API_KEY`            | Ollama Cloud key                   |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service-role key          |
| `VAPI_API_KEY`              | Vapi **private** key               |

**Non-secret config — plain env vars are fine:**

| Key                    | Notes                                            |
|------------------------|--------------------------------------------------|
| `LANGSMITH_PROJECT`    | e.g. `tsumiki-dev`                               |
| `LANGSMITH_TRACING`    | `true` to emit traces                            |
| `OLLAMA_MODEL`         | e.g. `gemma4:31b-cloud`                          |
| `SUPABASE_URL`         | project URL (host is public)                     |
| `VAPI_ASSISTANT_ID`    | assistant id                                     |
| `VAPI_PHONE_NUMBER_ID` | Vapi caller-ID id (required to place real calls) |
| `DEMO_USER_ID`         | optional, for the seeded demo user               |
| `DEMO_PHONE_NUMBER`    | optional, for `scripts/test_call.py`             |

Create the secrets (paste values interactively; they are not written to disk):

```bash
printf '%s' "PASTE_VALUE" | gcloud secrets create LANGSMITH_API_KEY --data-file=-
printf '%s' "PASTE_VALUE" | gcloud secrets create OLLAMA_API_KEY --data-file=-
printf '%s' "PASTE_VALUE" | gcloud secrets create SUPABASE_SERVICE_ROLE_KEY --data-file=-
printf '%s' "PASTE_VALUE" | gcloud secrets create VAPI_API_KEY --data-file=-
```

## 2. Deploy (build from source — Cloud Build uses the Dockerfile)

```bash
gcloud run deploy tsumiki-backend \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars "LANGSMITH_PROJECT=tsumiki-dev,LANGSMITH_TRACING=true,OLLAMA_MODEL=gemma4:31b-cloud,SUPABASE_URL=https://YOUR_PROJECT.supabase.co,VAPI_ASSISTANT_ID=YOUR_ASSISTANT_ID,VAPI_PHONE_NUMBER_ID=YOUR_PHONE_NUMBER_ID" \
  --set-secrets "LANGSMITH_API_KEY=LANGSMITH_API_KEY:latest,OLLAMA_API_KEY=OLLAMA_API_KEY:latest,SUPABASE_SERVICE_ROLE_KEY=SUPABASE_SERVICE_ROLE_KEY:latest,VAPI_API_KEY=VAPI_API_KEY:latest"
```

Cloud Run injects `$PORT`; the container's `CMD` already binds
`0.0.0.0:$PORT`, so no port flag is needed.

## 3. Verify

```bash
SERVICE_URL=$(gcloud run services describe tsumiki-backend \
  --region us-central1 --format 'value(status.url)')
curl "$SERVICE_URL/health"     # -> {"status":"ok", ...} (no secrets)
```

## 4. Wire the clients

- **Android app** (Google AI Studio): set its backend base URL to `$SERVICE_URL`.
- **Dashboard**: point it at `$SERVICE_URL` and enable Supabase Realtime per
  `docs/realtime_setup.md`.

## Notes

- Chroma uses a local persistent path inside the container (`CHROMA_PATH`); it is
  ephemeral per-instance on Cloud Run. For the demo that is fine. For durable
  vector memory, mount a volume or move to a hosted vector store.
- LLM/agent calls are network-bound — keep request timeouts generous and prefer
  the async/background pattern for anything that would otherwise block a client.
