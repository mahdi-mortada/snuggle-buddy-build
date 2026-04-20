# Ngrok Setup — Share CrisisShield with Teammates

> **Trigger phrase:** When the user says "set up ngrok", "share with teammates", or "enable ngrok" — follow the steps below. When the user says "revert ngrok", "stop sharing", or "go back to local" — follow the Revert section.

---

## Authtoken

```
3Cbycj11YblCtXy8dZS3KUMqGlD_3DkrpmdC21Y82jVsyzJFs
```

Location: `C:\Users\MahdiMortada\ngrok\ngrok.exe` (already installed and authenticated)

---

## Step 1 — Start ngrok tunnel on port 3002

```bash
$HOME/ngrok/ngrok.exe http 3002 --log=stdout > /tmp/ngrok.log 2>&1 &
sleep 5
```

Then get the public URL:

```bash
curl -s http://127.0.0.1:4040/api/tunnels | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'])"
```

Save this URL as `NGROK_URL` for the steps below.

---

## Step 2 — Edit 3 files

### File 1: `docker-compose.yml` (line ~178)

Change:
```yaml
VITE_BACKEND_URL: http://localhost:8010
VITE_BACKEND_WS_URL: ws://localhost:8010/ws/live-feed
```
To:
```yaml
VITE_BACKEND_URL: <NGROK_URL>
VITE_BACKEND_WS_URL: wss://<NGROK_URL_WITHOUT_HTTPS>/ws/live-feed
```

### File 2: `.env` (root, line ~7)

Change:
```env
VITE_BACKEND_URL="http://localhost:8010"
VITE_BACKEND_WS_URL="ws://localhost:8010/ws/live-feed"
```
To:
```env
VITE_BACKEND_URL="<NGROK_URL>"
VITE_BACKEND_WS_URL="wss://<NGROK_URL_WITHOUT_HTTPS>/ws/live-feed"
```

### File 3: `backend/.env` (CORS_ORIGINS line ~125)

Append the ngrok URL to the JSON array:
```
,"<NGROK_URL>"
```

---

## Step 3 — Rebuild frontend + restart backend

```bash
docker-compose up --build -d frontend backend
```

---

## Step 4 — Verify

```bash
curl -s <NGROK_URL>/health
curl -s <NGROK_URL>/assets/ | grep ngrok
```

Share the URL with teammates. Login: `admin@crisisshield.dev` / `admin12345`

---

## Revert — Go back to local

### Step 1 — Kill ngrok

```bash
taskkill //IM ngrok.exe //F
```

### Step 2 — Restore files

```bash
git checkout docker-compose.yml .env
```

For `backend/.env`, remove the ngrok URL from `CORS_ORIGINS` manually (this file is gitignored).

### Step 3 — Rebuild frontend

```bash
docker-compose up --build -d frontend backend
```

---

## Important notes

- The ngrok free plan gives a **random subdomain** that changes every time you restart ngrok
- **Do NOT commit** `docker-compose.yml` or `.env` while they have the ngrok URL
- The tunnel dies if you close the terminal or restart your machine
- First-time visitors see an ngrok interstitial page — they click "Visit Site" to proceed
- Only one tunnel is needed because nginx on port 3002 proxies `/api/` and `/ws/` to the backend
