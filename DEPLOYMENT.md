# Aegis Gold: Public Deployment Guide

This guide walks you through deploying the **Aegis Gold Quant Trading Platform** to a public URL so testers can access it and submit live feedback.

---

## Architecture Overview

```
 [ Next.js Dashboard ] (Public URL, e.g. Vercel)
         │
         │ (HTTPS / Secure WebSockets)
         ▼
 [ FastAPI Backend ]  (Public URL, e.g. Render)
```

---

## 1. Deploy the Backend (FastAPI) on Render

Render is the recommended choice because it fully supports Python background threads (needed for our 1-second quant streaming loop).

### Step-by-Step:
1. **Sign Up / Log In**: Go to [Render](https://render.com) and connect your GitHub account.
2. **Create Web Service**: Click **New +** and select **Web Service**.
3. **Select Repository**: Select the `Aegis` repository.
4. **Configure Settings**:
   * **Name**: `aegis-gold-api`
   * **Language**: `Python 3`
   * **Build Command**: `pip install -r requirements.txt`
   * **Start Command**: `PYTHONPATH=. uvicorn src.api.server:app --host 0.0.0.0 --port $PORT`
5. **Add Environment Variables**:
   Click on the **Environment** tab and add the following keys:
   * `ENV` = `development` (loads development configs, SQLite)
   * `DATABASE_URL` = `sqlite:///./quant_trading.db`
   * `JWT_SECRET` = `your_super_secret_jwt_key`
   * `GEMINI_API_KEY` = `your_gemini_api_key`
   * `GOLDAPI_KEY` = `your_goldapi_key`
6. **Deploy**: Click **Create Web Service**. 
   * *Once deployed, Render will provide a public URL like `https://aegis-gold-api.onrender.com`.*

---

## 2. Deploy the Frontend (Next.js) on Vercel

Vercel is the optimized hosting platform for Next.js web applications.

### Step-by-Step:
1. **Sign Up / Log In**: Go to [Vercel](https://vercel.com) and link your GitHub account.
2. **Import Project**: Click **Add New** -> **Project** and import the `Aegis` repository.
3. **Configure Project Settings**:
   * **Root Directory**: Select the `dashboard` folder.
   * **Framework Preset**: `Next.js`
4. **Add Environment Variables**:
   Under **Environment Variables**, add:
   * `NEXT_PUBLIC_API_URL` = `https://aegis-gold-api.onrender.com` (Your public backend Render URL)
   * `NEXT_PUBLIC_WS_URL` = `wss://aegis-gold-api.onrender.com` (Note the **`wss://`** protocol for secure websockets)
5. **Deploy**: Click **Deploy**.
   * *Vercel will build and assign a public address (e.g. `https://aegis-gold-dashboard.vercel.app`).*

---

## 3. Inviting Testers & Collecting Feedback

1. Give the Vercel URL to your testers.
2. Testers can login with the preset credentials (e.g., username `admin`, password `admin_password` or `trader` / `trader_password`).
3. Testers can navigate the live streaming dashboard, trigger paper executions, look at Kalman trend lines and Gemini market commentary.
4. Testers can click **Submit Feedback** in the sidebar to open the glassmorphic feedback modal, input their rating/comments, and submit.
5. All feedback will be recorded in the live SQLite database in Render.
