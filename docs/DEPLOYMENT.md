# Deployment (India-first)

Target: close to zero cost when idle, pay mostly per interview, scale without re-architecture.
Regions are Mumbai wherever the provider offers it, because voice latency depends on distance.

| Component | Service | Region |
|---|---|---|
| Web (`apps/web`) | Vercel (Pro plan once the product charges users) | Global CDN |
| API (`services/api`) | Google Cloud Run | `asia-south1` (Mumbai) |
| Database, file storage, auth | Supabase (Postgres, Storage, Auth) | `ap-south-1` (Mumbai) |
| Realtime media | LiveKit Cloud | Nearest to India |
| Voice agent (`services/agent`) | LiveKit Cloud agent hosting (fallback: GCE managed instance group) | Same as LiveKit |
| DNS, TLS, domain | Cloudflare | Global |
| Errors / LLM traces | Sentry, Langfuse | - |

## Environments

- **local**: `docker compose up` or the per-service commands in the README.
- **staging**: auto-deploys from the `staging` branch; separate Supabase project and keys.
- **production**: deploys from `main` after CI passes.

## 1. Supabase

1. Create a project in the Mumbai region.
2. Auth: enable Google sign-in (step by step: [GOOGLE_SIGN_IN.md](GOOGLE_SIGN_IN.md)).
3. Storage: create a private bucket `resumes`, and create S3 access keys (Storage settings).
4. Note the connection string (use the **pooler** URL for Cloud Run) and the project URL. The
   API verifies sign-in tokens with the project's public signing keys (JWKS at `SUPABASE_URL`).

## 2. API on Cloud Run

Secrets go in Secret Manager, not in the image:

```bash
gcloud secrets create anthropic-api-key --data-file=-     # paste key, Ctrl-D
# repeat for: database-url, jwt-secret, internal-api-key, livekit-api-secret, s3-secret
```

Build and deploy:

```bash
cd services/api
gcloud run deploy mycareer-api \
  --source . --region asia-south1 --allow-unauthenticated \
  --min-instances 0 --max-instances 10 --memory 1Gi \
  --no-cpu-throttling \
  --set-env-vars ENVIRONMENT=production,AUTH_MODE=supabase,STORAGE_BACKEND=s3,\
SUPABASE_URL=https://YOUR-PROJECT.supabase.co,\
CORS_ORIGINS=https://YOUR-DOMAIN,LIVEKIT_URL=wss://YOUR-PROJECT.livekit.cloud,\
LIVEKIT_API_KEY=YOUR_KEY,LIVEKIT_AGENT_NAME=mycareer-interviewer,\
S3_BUCKET=resumes,S3_ENDPOINT_URL=https://YOUR-PROJECT.supabase.co/storage/v1/s3,\
S3_ACCESS_KEY_ID=YOUR_ID,S3_REGION=ap-south-1 \
  --set-secrets ANTHROPIC_API_KEY=anthropic-api-key:latest,DATABASE_URL=database-url:latest,\
JWT_SECRET=jwt-secret:latest,INTERNAL_API_KEY=internal-api-key:latest,\
LIVEKIT_API_SECRET=livekit-api-secret:latest,S3_SECRET_ACCESS_KEY=s3-secret:latest
```

`--no-cpu-throttling` matters: planning and evaluation run as background tasks after the HTTP
response returns, and Cloud Run would otherwise throttle the CPU. When volume grows, move these
jobs to Cloud Tasks.

Run migrations before each deploy that changes the schema, for example as a Cloud Run Job
using the same image:

```bash
gcloud run jobs deploy mycareer-migrate --image IMAGE_FROM_ABOVE --region asia-south1 \
  --set-secrets DATABASE_URL=database-url:latest --command alembic --args upgrade,head
gcloud run jobs execute mycareer-migrate --region asia-south1 --wait
```

## 3. LiveKit Cloud and the voice agent

1. Create a LiveKit Cloud project and note the URL, API key and secret.
2. Deploy `services/agent` with LiveKit Cloud agent hosting (see the LiveKit docs on
   deploying agents; the `Dockerfile` in `services/agent` is ready for it). Set:
   `LIVEKIT_AGENT_NAME=mycareer-interviewer`, `API_BASE_URL=https://<cloud-run-url>`,
   `INTERNAL_API_KEY`, `ANTHROPIC_API_KEY`, `DEEPGRAM_API_KEY`.
3. Fallback if hosting there doesn't fit: run the same image on a small GCE managed instance
   group in `asia-south1` with `python -m interviewer.main start`. Each worker handles several
   concurrent interviews; scale on CPU.

## 4. Web on Vercel

1. Import the repo and set the root directory to `apps/web`.
2. Set `NEXT_PUBLIC_API_URL=https://api.YOUR-DOMAIN` (map a custom domain to Cloud Run),
   `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`, and
   `NEXT_PUBLIC_DEV_LOGIN=false`.
3. Add the domain in Vercel and point DNS at it from Cloudflare.

## Cost model

Fixed infrastructure is mostly free tiers or scale-to-zero at MVP volume. The variable cost per
interview is driven by:

- speech-to-text and text-to-speech minutes (Deepgram)
- LLM tokens: the fast model for each live turn, the smart model once for planning and once per
  evaluation
- LiveKit participant/agent minutes

Measure the real cost of a 45-minute round in staging (provider dashboards and Langfuse) before
setting prices.
