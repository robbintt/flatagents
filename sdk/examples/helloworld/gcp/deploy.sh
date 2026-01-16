#!/bin/bash
# Deploy FlatAgents Helloworld to Google Cloud Functions
#
# Prerequisites:
#   - gcloud CLI installed and authenticated
#   - A GCP project with billing enabled
#   - Firestore in Native mode enabled
#
# Usage:
#   export LLM_API_KEY=your-api-key
#   ./deploy.sh

set -e

# Configuration
FUNCTION_NAME="${FUNCTION_NAME:-flatagents-helloworld}"
REGION="${REGION:-us-central1}"
RUNTIME="python311"
TIMEOUT="60s"
MEMORY="512MB"

# Check for required env vars
if [ -z "$LLM_API_KEY" ]; then
    echo "Error: LLM_API_KEY environment variable is required"
    echo "Export your OpenAI/Cerebras/etc API key:"
    echo "  export LLM_API_KEY=your-key"
    exit 1
fi

# Get the directory of this script
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Deploying $FUNCTION_NAME to $REGION..."

# Deploy
gcloud functions deploy "$FUNCTION_NAME" \
    --gen2 \
    --runtime="$RUNTIME" \
    --region="$REGION" \
    --source="$SCRIPT_DIR" \
    --entry-point=helloworld \
    --trigger-http \
    --allow-unauthenticated \
    --timeout="$TIMEOUT" \
    --memory="$MEMORY" \
    --set-env-vars="LLM_API_KEY=$LLM_API_KEY,FIRESTORE_COLLECTION=flatagents-helloworld"

echo ""
echo "Deployment complete!"
echo ""
echo "Get your function URL with:"
echo "  gcloud functions describe $FUNCTION_NAME --region=$REGION --format='value(serviceConfig.uri)'"
echo ""
echo "Test it with:"
echo '  curl -X POST $URL -H "Content-Type: application/json" -d '"'"'{"target": "Hi"}'"'"
