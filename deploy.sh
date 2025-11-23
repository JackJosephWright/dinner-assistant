#!/bin/bash

# Deployment script for Google Cloud Run
# Prerequisites:
# 1. Install Google Cloud CLI: https://cloud.google.com/sdk/docs/install
# 2. Run: gcloud auth login
# 3. Set your ANTHROPIC_API_KEY in the command below

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

# Set project
echo "📋 Setting project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo "🔧 Enabling required APIs..."
gcloud services enable run.googleapis.com
gcloud services enable containerregistry.googleapis.com

# Build and push container image
echo "🏗️  Building container image..."
gcloud builds submit --tag $IMAGE_NAME

# Deploy to Cloud Run
echo "☁️  Deploying to Cloud Run..."
gcloud run deploy $SERVICE_NAME \
  --image $IMAGE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 4Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 1 \
  --set-env-vars "ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-YOUR_API_KEY_HERE}" \
  --set-env-vars "FLASK_SECRET_KEY=$(openssl rand -hex 32)"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "🌐 Your app URL:"
gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'
echo ""
echo "⚠️  IMPORTANT NOTES:"
echo "1. Set your ANTHROPIC_API_KEY before deploying:"
echo "   export ANTHROPIC_API_KEY='your-key-here'"
echo "   ./deploy.sh"
echo ""
echo "2. User data will be reset on each deployment (ephemeral storage)"
echo "   To persist data, consider adding Cloud Storage or Cloud SQL"
echo ""
echo "3. Login credentials:"
echo "   - Username: admin, Password: password"
echo "   - Username: agusta, Password: password"
echo ""
