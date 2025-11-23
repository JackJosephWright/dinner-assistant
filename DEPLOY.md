# Deployment Guide - Google Cloud Run

## Quick Start

1. **Install Google Cloud CLI** (if not already installed):
   ```bash
   # macOS
   brew install google-cloud-sdk

   # Linux/WSL
   curl https://sdk.cloud.google.com | bash
   exec -l $SHELL
   ```

2. **Login to Google Cloud**:
   ```bash
   gcloud auth login
   gcloud auth configure-docker
   ```

3. **Set your API key**:
   ```bash
   export ANTHROPIC_API_KEY='your-actual-api-key-here'
   ```

4. **Deploy**:
   ```bash
   ./deploy.sh
   ```

That's it! The script will:
- Build your Docker container
- Push it to Google Container Registry
- Deploy to Cloud Run
- Output your live URL

## What's Included

✅ **Recipe Database**: `recipes.db` (2.2GB, 492,630 recipes - 5K enriched)
✅ **User Data**: `user_data.db` (4.9MB, preferences and history)
✅ **Web Interface**: Full Flask app with Plan/Shop/Cook tabs
✅ **Authentication**: admin/password and agusta/password

## Cost Estimate

**Google Cloud Run Free Tier:**
- 2 million requests/month
- 360,000 GB-seconds/month
- 180,000 vCPU-seconds/month

**Estimated cost for low traffic (<100 requests/day):** ~$5-15/month (due to 4GB RAM allocation)

**Anthropic API costs:**
- Planning a meal: ~$0.01-0.02
- Creating shopping list: ~$0.01
- Chat responses: ~$0.005-0.02

## Important Notes

⚠️ **Ephemeral Storage**: User data (meal plans, shopping lists) will reset on each deployment. To persist data:
- Option A: Add Cloud Storage bucket
- Option B: Migrate to Cloud SQL
- Option C: Accept resets (users can recreate plans quickly)

⚠️ **Database Size**: The container includes a 2.2GB recipe database with 492K recipes. First deployment will take ~10-15 minutes to upload.

⚠️ **Memory**: Configured for 4GB RAM to handle the large recipe database and AI agents.

## Customization

Edit `deploy.sh` to change:
- `REGION`: Change from `us-central1` to your preferred region
- `--memory`: Adjust RAM allocation (default 4Gi for full database, min 2Gi, max 8Gi)
- `--max-instances`: Set max concurrent instances (default 10)
- `--set-env-vars`: Add/modify environment variables

## Updating Passwords

To change login credentials, edit `src/web/app.py`:

```python
USERS = {
    "admin": "your-secure-password",
    "agusta": "another-secure-password"
}
```

Then redeploy with `./deploy.sh`

## Troubleshooting

**Build fails with "permission denied"**:
```bash
chmod +x deploy.sh
```

**"gcloud: command not found"**:
Install Google Cloud CLI (see step 1)

**"ANTHROPIC_API_KEY not set"**:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
./deploy.sh
```

**Container too large**:
The 2.2GB database is included. First push takes ~10-15 minutes depending on your upload speed. Subsequent deploys are faster due to Docker layer caching.

## Next Steps

After deployment:
1. Visit the URL provided by the script
2. Login with admin/password or agusta/password
3. Complete the onboarding flow
4. Start planning meals!

## Monitoring

View logs:
```bash
gcloud run services logs read dinner-assistant --region us-central1
```

View metrics:
```bash
gcloud run services describe dinner-assistant --region us-central1
```
