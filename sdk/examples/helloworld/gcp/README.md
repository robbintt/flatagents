# FlatAgents Helloworld - Google Cloud Functions

Deploy the FlatAgents helloworld example to Google Cloud Functions with Firestore persistence.

## Prerequisites

You'll need:
- A Google Cloud account (free tier works!)
- `gcloud` CLI installed
- An LLM API key (OpenAI, Cerebras, etc.)

## Quick Start (5 minutes)

### 1. Install gcloud CLI

**macOS:**
```bash
brew install google-cloud-sdk
```

**Linux/Windows:** See [gcloud install guide](https://cloud.google.com/sdk/docs/install)

### 2. Authenticate and set up project

```bash
# Login to Google Cloud
gcloud auth login

# Create a new project (or use existing)
gcloud projects create flatagents-demo --name="FlatAgents Demo"
gcloud config set project flatagents-demo

# Enable required APIs (one-time, takes ~1 min)
gcloud services enable cloudfunctions.googleapis.com
gcloud services enable cloudbuild.googleapis.com
gcloud services enable firestore.googleapis.com
gcloud services enable run.googleapis.com
```

### 3. Create Firestore database

```bash
# Create Firestore in Native mode (required for this backend)
gcloud firestore databases create --location=us-central1
```

### 4. Deploy

```bash
cd sdk/examples/helloworld/gcp

# Set your LLM API key
export LLM_API_KEY=your-openai-or-cerebras-key

# Deploy (takes ~2 min first time)
chmod +x deploy.sh
./deploy.sh
```

### 5. Test it

```bash
# Get your function URL
URL=$(gcloud functions describe flatagents-helloworld \
  --region=us-central1 \
  --format='value(serviceConfig.uri)')

# Call it!
curl -X POST "$URL" \
  -H "Content-Type: application/json" \
  -d '{"target": "Hi"}'
```

Expected response:
```json
{"result": "Hi", "success": true, "execution_id": "abc-123"}
```

---

## Local Testing (No Docker!)

You can test locally using `functions-framework`:

```bash
cd sdk/examples/helloworld/gcp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies (includes local flatagents)
pip install -e ../../../python  # Install flatagents from source
pip install -r requirements.txt

# Set environment variables
export LLM_API_KEY=your-key
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Run locally (no Docker, no containers!)
functions-framework --target=helloworld --port=8080
```

Test in another terminal:
```bash
curl -X POST http://localhost:8080 \
  -H "Content-Type: application/json" \
  -d '{"target": "Hi"}'
```

### Using Firestore Emulator (fully offline)

For completely offline testing:

```bash
# Install Firebase CLI (includes emulator)
npm install -g firebase-tools

# Start Firestore emulator (no Docker needed)
firebase emulators:start --only firestore --project=demo-project

# In another terminal, point your app at the emulator
export FIRESTORE_EMULATOR_HOST=localhost:8080
export GOOGLE_CLOUD_PROJECT=demo-project

# Run your function locally
functions-framework --target=helloworld --port=8081
```

---

## Costs

This example stays well within GCP's free tier:

| Resource | Free Tier | This Example |
|----------|-----------|--------------|
| Cloud Functions | 2M invocations/month | ~1 per test |
| Firestore reads | 50K/day | ~10 per run |
| Firestore writes | 20K/day | ~10 per run |

**Estimated cost: $0** for normal usage.

---

## Cleanup

Delete everything when you're done:

```bash
# Delete the Cloud Function
gcloud functions delete flatagents-helloworld --region=us-central1

# Delete Firestore data (optional - it's free to keep)
# This deletes ALL data in the flatagents-helloworld collection
gcloud firestore documents delete \
  --collection-ids=flatagents-helloworld \
  --recursive

# Or delete the entire project
gcloud projects delete flatagents-demo
```

---

## Scheduled Cleanup (Optional)

To automatically delete old Firestore documents, create a cleanup function:

```bash
# Deploy cleanup function (runs daily at midnight)
gcloud functions deploy flatagents-cleanup \
  --gen2 \
  --runtime=python311 \
  --trigger-http \
  --entry-point=cleanup \
  --source=.

# Create Cloud Scheduler job (free tier: 3 jobs)
gcloud scheduler jobs create http flatagents-cleanup-daily \
  --schedule="0 0 * * *" \
  --uri="$CLEANUP_URL" \
  --http-method=POST
```

---

## Troubleshooting

### "Permission denied" errors

Make sure you've enabled the required APIs:
```bash
gcloud services enable cloudfunctions.googleapis.com cloudbuild.googleapis.com
```

### "Firestore not found" errors

Create the Firestore database first:
```bash
gcloud firestore databases create --location=us-central1
```

### Cold start takes too long

The first request after deployment takes 5-10 seconds (cold start). Subsequent requests are faster (~1-2 seconds).

### LLM API errors

Check your `LLM_API_KEY` is set correctly:
```bash
gcloud functions describe flatagents-helloworld \
  --region=us-central1 \
  --format='value(serviceConfig.environmentVariables.LLM_API_KEY)'
```
