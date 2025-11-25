#!/bin/bash

# Deployment script for Google Cloud Run
# Prerequisites:
# 1. Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
# 2. Run: gcloud auth login
# 3. Set your ANTHROPIC_API_KEY environment variable

set -e

# Configuration
PROJECT_ID="dinner-assistant-479014"
REGION="us-central1"
SERVICE_NAME="dinner-assistant"
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

echo "🚀 Deploying Dinner Assistant to Google Cloud Run..."
echo "Project: $PROJECT_ID"
echo "Region: $REGION"
echo "Service: $SERVICE_NAME"
echo ""

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI not found. Please install it first:"
    echo "   https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# Check for API key
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ Error: ANTHROPIC_API_KEY environment variable not set"
    echo "   export ANTHROPIC_API_KEY='your-key-here'"
    exit 1
fi

# Set project
echo "📋 Setting project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and push container image
echo "🏗️  Building container image..."
echo "   (Using dev database: 1.2GB instead of 2.2GB)"
gcloud builds submit --tag $IMAGE_NAME

# Generate service.yaml with substituted env vars
echo "📝 Preparing service configuration..."
FLASK_SECRET_KEY=$(openssl rand -hex 32)
export ANTHROPIC_API_KEY
export FLASK_SECRET_KEY

# Create temporary service file with substituted values
envsubst < service.yaml > /tmp/service-deploy.yaml

# Deploy using service.yaml (includes tuned health probes)
echo "☁️  Deploying to Cloud Run with custom health probes..."
gcloud run services replace /tmp/service-deploy.yaml \
  --region $REGION

# Make service publicly accessible
echo "🔓 Allowing unauthenticated access..."
gcloud run services add-iam-policy-binding $SERVICE_NAME \
  --region $REGION \
  --member="allUsers" \
  --role="roles/run.invoker"

# Cleanup
rm -f /tmp/service-deploy.yaml

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your app URL:"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
echo ""
echo "📊 Deployment details:"
echo "   - Workers: 2 (up from 1)"
echo "   - Threads: 8 per worker"
echo "   - Database: dev (5K enriched recipes)"
echo "   - Health probe: 10s timeout, 30s period, 5 failures allowed"
echo ""
echo "🔑 Login credentials:"
echo "   - Username: admin, Password: password"
echo "   - Username: agusta, Password: password"
echo ""
