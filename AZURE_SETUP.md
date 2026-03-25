# Azure Setup Guide — Predictive Maintenance Multi-Agent System

This guide walks you through deploying the app to **Azure App Service** from scratch.
No Azure experience required — every step includes the exact Portal URL to open.

**Time to complete:** ~45 minutes
**Cost (B1 App Service + Basic Redis + Burstable PostgreSQL):** ~€35–45 / month

---

## Prerequisites

- A GitHub account with this repository pushed to it
- A credit card (required even for the free tier; you will not be charged if you stay within free limits)

---

## Step 1 — Create an Azure Account and Activate Free Credits

**URL:** https://azure.microsoft.com/en-us/free

1. Click **Start free**.
2. Sign in with a Microsoft account (or create one).
3. Complete identity verification with your phone and credit card.
4. After sign-up you receive **$200 / €200 free credits** valid for 30 days plus always-free service tiers.
5. You land on the **Azure Portal** at https://portal.azure.com — bookmark it.

---

## Step 2 — Create a Resource Group

A resource group is a logical container for all Azure resources belonging to this project.

**URL:** https://portal.azure.com/#create/Microsoft.ResourceGroup

1. Click **+ Create**.
2. Fill in:
   | Field | Value |
   |-------|-------|
   | Subscription | Your subscription (e.g. "Azure subscription 1") |
   | Resource group name | `rg-pred-maintenance` |
   | Region | **(Europe) West Europe** |
3. Click **Review + create** → **Create**.
4. Click **Go to resource group** when the notification appears.

> **Why West Europe?** The target market is Stuttgart industrial customers (Bosch, Mercedes-Benz, ZF). West Europe (Amsterdam) gives the lowest latency for Germany.

---

## Step 3 — Create an App Service Plan

The plan defines the VM size that runs your app.

**URL:** https://portal.azure.com/#create/Microsoft.AppServicePlanCreate

1. Fill in:
   | Field | Value |
   |-------|-------|
   | Subscription | Your subscription |
   | Resource group | `rg-pred-maintenance` |
   | Name | `pred-maint-plan` |
   | Operating System | **Linux** |
   | Region | **West Europe** |
   | Pricing plan | **Basic B1** (click "Explore pricing plans" → Basic → B1) |
2. Click **Review + create** → **Create**.

> **Why B1?** 1 vCPU / 1.75 GB RAM is enough for the 2-worker gunicorn setup. Scale up to P1v3 when you add real sensor traffic.

---

## Step 4 — Create the Web App

**URL:** https://portal.azure.com/#create/Microsoft.WebSite

1. Fill in:
   | Field | Value |
   |-------|-------|
   | Subscription | Your subscription |
   | Resource group | `rg-pred-maintenance` |
   | Name | `pred-maint-app` *(must be globally unique — Azure adds `.azurewebsites.net`)* |
   | Publish | **Code** |
   | Runtime stack | **Python 3.12** |
   | Operating System | **Linux** |
   | Region | **West Europe** |
   | Linux Plan | Select `pred-maint-plan` (created in Step 3) |
2. Leave all other tabs at their defaults.
3. Click **Review + create** → **Create**.
4. When deployment finishes, click **Go to resource** — this is your App Service blade.

---

## Step 5 — Configure Environment Variables

Your app reads secrets from environment variables. Set them here so they are never in source code.

**URL:** https://portal.azure.com → your App Service → **Settings → Environment variables**

*(Older Portal: Configuration → Application settings → + New application setting)*

Add each of the following key/value pairs by clicking **+ Add**:

| Name | Value | Required |
|------|-------|----------|
| `ANTHROPIC_API_KEY` | `sk-ant-api03-...` (from https://console.anthropic.com/settings/keys) | **Yes** |
| `ENVIRONMENT` | `production` | Yes |
| `REDIS_URL` | `redis://<host>:6380?ssl=True&password=<key>` (filled in Step 9) | Yes |
| `DATABASE_URL` | `postgresql+asyncpg://<user>:<pass>@<host>:5432/predictive_maintenance?ssl=require` (filled in Step 10) | Yes |
| `LANGFUSE_SECRET_KEY` | Your Langfuse secret key — leave blank if not using Langfuse | No |
| `LANGFUSE_PUBLIC_KEY` | Your Langfuse public key — leave blank if not using Langfuse | No |

After adding all settings, click **Apply** at the bottom of the page, then **Confirm**.

> **Important:** the app will restart after you click Apply. That is expected.

---

## Step 6 — Set the Startup Command

**URL:** https://portal.azure.com → your App Service → **Settings → Configuration → General settings**

1. Scroll to **Startup Command**.
2. Paste exactly:
   ```
   gunicorn src.api.main:app --workers 2 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```
3. Click **Save** → **Continue** when prompted.

> This command is also stored in `startup.sh` in the repository for reference.

---

## Step 7 — Connect GitHub for Auto-Deployment

Every push to `main` will automatically deploy via the CI/CD pipeline in `.github/workflows/deploy.yml`.

**URL:** https://portal.azure.com → your App Service → **Deployment → Deployment Center**

1. Under **Source**, select **GitHub**.
2. Click **Authorize** and sign in to GitHub when prompted.
3. Fill in:
   | Field | Value |
   |-------|-------|
   | Organization | Your GitHub username or org |
   | Repository | `predictive_maintaince_agent` (or whatever you named it) |
   | Branch | `main` |
4. Under **Workflow option**, select **Add a workflow** — this lets our existing `deploy.yml` handle deployment rather than Azure generating a new one.

   > If Azure offers to generate a workflow file, choose **Use existing workflow** instead.

5. Click **Save**.

---

## Step 8 — Add the Publish Profile Secret to GitHub

The GitHub Actions workflow authenticates to Azure using a publish profile.

### Download the publish profile

**URL:** https://portal.azure.com → your App Service → Overview

1. Click **Download publish profile** in the top toolbar.
2. A `.PublishSettings` XML file downloads — **keep this file secret**.

### Add it as a GitHub secret

**URL:** https://github.com/YOUR_USERNAME/YOUR_REPO/settings/secrets/actions

1. Click **New repository secret**.
2. Fill in:
   | Field | Value |
   |-------|-------|
   | Name | `AZURE_WEBAPP_PUBLISH_PROFILE` |
   | Secret | Paste the **entire contents** of the downloaded `.PublishSettings` file |
3. Click **Add secret**.

Now every push to `main` will run tests and, if they pass, deploy to Azure automatically.

---

## Step 9 — Create Azure Cache for Redis

Redis is the inter-agent event bus.

**URL:** https://portal.azure.com/#create/Microsoft.Cache.Redis

1. Fill in:
   | Field | Value |
   |-------|-------|
   | Subscription | Your subscription |
   | Resource group | `rg-pred-maintenance` |
   | DNS name | `pred-maint-redis` *(must be globally unique)* |
   | Location | **West Europe** |
   | Cache SKU | **Basic** |
   | Cache size | **C0 (250 MB)** |
2. Click **Review + create** → **Create**.
   > Provisioning takes ~10–15 minutes.

### Get the connection string

**URL:** https://portal.azure.com → your Redis cache → **Settings → Authentication** → **Access keys**

1. Copy the **Primary connection string (StackExchange.Redis)**.
   It looks like: `pred-maint-redis.redis.cache.windows.net:6380,password=ABC123...,ssl=True,abortConnect=False`
2. Convert it to the format your app expects:
   ```
   redis://pred-maint-redis.redis.cache.windows.net:6380?ssl=True&password=ABC123...
   ```
3. Go back to Step 5 and update the `REDIS_URL` app setting with this value.

---

## Step 10 — Create Azure Database for PostgreSQL

PostgreSQL stores maintenance tickets and event logs.

**URL:** https://portal.azure.com/#create/Microsoft.PostgreSQLFlexibleServer

1. Fill in:
   | Field | Value |
   |-------|-------|
   | Subscription | Your subscription |
   | Resource group | `rg-pred-maintenance` |
   | Server name | `pred-maint-db` *(must be globally unique)* |
   | Region | **West Europe** |
   | PostgreSQL version | **16** |
   | Workload type | **Development** |
   | Compute + storage | Click **Configure server** → **Burstable** → **B1ms** (1 vCore / 2 GB) |
   | Admin username | `pgadmin` *(or your choice — write it down)* |
   | Password | A strong password — write it down |
2. On the **Networking** tab:
   - Connectivity method: **Public access**
   - Check **Allow public access from any Azure service within Azure to this server**
   - Click **+ Add current client IP** if you want to connect from your laptop too
3. Click **Review + create** → **Create**.
   > Provisioning takes ~5–10 minutes.

### Create the application database

**URL:** https://portal.azure.com → your PostgreSQL server → **Settings → Databases**

1. Click **+ Add**.
2. Set Database name to `predictive_maintenance`.
3. Click **Save**.

### Get the connection string

**URL:** https://portal.azure.com → your PostgreSQL server → **Settings → Connect**

1. Select the **Python** tab.
2. Copy the connection string. It looks like:
   ```
   host=pred-maint-db.postgres.database.azure.com port=5432 dbname=predictive_maintenance user=pgadmin password=<your-password> sslmode=require
   ```
3. Rewrite it in the `asyncpg` URL format your app expects:
   ```
   postgresql+asyncpg://pgadmin:<your-password>@pred-maint-db.postgres.database.azure.com:5432/predictive_maintenance?ssl=require
   ```
4. Go back to Step 5 and update the `DATABASE_URL` app setting with this value.

---

## Step 11 — Verify the Deployment

Give the pipeline a moment after your first push to `main` completes, then:

**Health check:**
```
https://pred-maint-app.azurewebsites.net/health
```

Expected response:
```json
{
  "status": "ok",
  "agents_count": 4,
  "mcp_servers_count": 3
}
```

**Failure modes endpoint:**
```
https://pred-maint-app.azurewebsites.net/failure-modes
```

**Run a simulated analysis (use curl or Postman):**
```bash
curl -X POST https://pred-maint-app.azurewebsites.net/simulate/PUMP-001 \
  -H "Content-Type: application/json" \
  -d '{"equipment_id": "PUMP-001", "anomaly_type": "bearing_wear", "reading_count": 100}'
```

### Troubleshooting

If the health check returns 500 or the app won't start:

1. **Check logs:**
   **URL:** https://portal.azure.com → your App Service → **Monitoring → Log stream**

2. **Common issues:**
   | Symptom | Fix |
   |---------|-----|
   | `ANTHROPIC_API_KEY` missing | Re-check Step 5; confirm the setting name is exact |
   | `ModuleNotFoundError` | Confirm `.deployment` file is in the repo root with `SCM_DO_BUILD_DURING_DEPLOYMENT=true` |
   | 502 Bad Gateway on startup | App is still cold-starting — wait 60 seconds and retry |
   | `connection refused` on Redis/Postgres | Firewall rule missing — re-check networking steps in Steps 9 and 10 |

3. **Force a redeploy:**
   **URL:** https://portal.azure.com → your App Service → **Deployment → Deployment Center** → **Sync**

---

## Cost Estimate (West Europe, monthly)

| Resource | SKU | Est. cost |
|----------|-----|-----------|
| App Service | B1 Linux | ~€12 |
| Azure Cache for Redis | Basic C0 | ~€15 |
| Azure Database for PostgreSQL | Burstable B1ms | ~€12 |
| Azure Monitor | Free tier (5 GB/month) | €0 |
| **Total** | | **~€39 / month** |

To stop all charges: delete the resource group `rg-pred-maintenance` — this removes every resource inside it at once.

**URL:** https://portal.azure.com → Resource groups → `rg-pred-maintenance` → **Delete resource group**
