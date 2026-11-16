# Shawarar Lafiya AI — Deployment Guide

> **Version:** 1.1.0  
> **Last Updated:** November 2026  
> **Stack:** Python 3.11+, FastAPI, Uvicorn, Google Gemini 2.5 Flash

---

## Prerequisites

| Requirement | Minimum Version | Purpose |
|---|---|---|
| Python | 3.11 | Runtime |
| pip / uv | latest | Package management |
| Gemini API Key | — | AI clinical triage engine |
| Twilio Account | — | Optional: WhatsApp + IVR |

---

## 1. Local Development Setup

```bash
# 1. Clone the repository
git clone https://github.com/YaryaskidJr/Shawarar-Lafiya-AI.git
cd "Shawarar Lafiya AI"

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and fill in GEMINI_API_KEY at minimum

# 5. Start the development server
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

# 6. Open the web UI
# → http://127.0.0.1:8000/ui
```

---

## 2. Required Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | ✅ For AI mode | `""` | Google Gemini API key. Leave blank for offline WHO IMCI mode. |
| `APP_ENV` | ⚠️ Production | `development` | Set to `production` in deployed environments. |
| `DEBUG` | ⚠️ Production | `false` | Must be `false` in production to prevent stack trace exposure. |
| `CORS_ORIGINS` | ⚠️ Production | `*` | Comma-separated allowed origins. Must NOT be `*` in production. |
| `TWILIO_ACCOUNT_SID` | Optional | `""` | Twilio SID for WhatsApp/IVR channel. |
| `TWILIO_AUTH_TOKEN` | Optional | `""` | Twilio Auth Token. |
| `TWILIO_WHATSAPP_NUMBER` | Optional | `""` | Twilio WhatsApp sender number (e.g. `whatsapp:+14155238886`). |
| `TWILIO_VOICE_NUMBER` | Optional | `""` | Twilio IVR voice number. |
| `DHIS2_BASE_URL` | Optional | `https://dhis2.nigeria.gov.ng/api` | DHIS2 instance for real-time PHC referral. |
| `DHIS2_USERNAME` | Optional | `""` | DHIS2 credentials. |
| `DHIS2_PASSWORD` | Optional | `""` | DHIS2 credentials. |
| `AUDIO_UPLOAD_DIR` | Optional | `uploads` | Directory for temporary audio file uploads. |

---

## 3. Production Deployment

### 3.1 Recommended: Uvicorn + Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run with 4 workers (adjust to 2 × CPU cores)
APP_ENV=production DEBUG=false CORS_ORIGINS=https://yourapp.com \
  gunicorn app.main:app \
  --workers 4 \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8000 \
  --access-logfile - \
  --error-logfile -
```

### 3.2 Systemd Service (Linux)

```ini
# /etc/systemd/system/shawarar-lafiya.service
[Unit]
Description=Shawarar Lafiya AI Backend
After=network.target

[Service]
User=shawarar
WorkingDirectory=/opt/shawarar-lafiya
EnvironmentFile=/opt/shawarar-lafiya/.env
ExecStart=/opt/shawarar-lafiya/venv/bin/gunicorn app.main:app \
    --workers 4 --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
systemctl enable shawarar-lafiya
systemctl start shawarar-lafiya
```

### 3.3 Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name yourapp.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourapp.com;

    ssl_certificate /etc/letsencrypt/live/yourapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourapp.com/privkey.pem;

    # Security headers (add-on to app-level headers)
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        # Webhook timeout for Twilio
        proxy_read_timeout 30s;
        client_max_body_size 10M;
    }
}
```

---

## 4. Health Check

```bash
curl http://127.0.0.1:8000/health
# Expected: {"status":"healthy","env":"production",...}
```

---

## 5. Running Tests

```bash
# Full test suite (must all pass before deployment)
python -m pytest -v --tb=short

# Clinical accuracy benchmark
python tests/evaluate_dataset.py

# Syntax check
python -m compileall app tests
```

**Expected:** 50 passed, 0 errors, 10/10 benchmark cases.

---

## 6. Known Limitations (MVP Stage)

| Limitation | Severity | Mitigation |
|---|---|---|
| ASR is simulated (no real speech-to-text) | Medium | Audio triage returns deterministic mock. Integrate Google STT for production voice. |
| Offline PHC dataset covers only 23 North Nigerian facilities | Medium | Extend `OFFLINE_PHC_DATA` in `referral_service.py` or configure DHIS2. |
| No rate limiting on API endpoints | Medium | Add `slowapi` or deploy behind a reverse proxy with rate limiting (Nginx `limit_req`). |
| WhatsApp language detection by phone prefix only | Low | Acceptable for MVP; refine with user preference storage. |

---

## 7. Security Checklist (Pre-Production)

- [ ] `GEMINI_API_KEY` stored in environment, NOT in code
- [ ] `APP_ENV=production` set
- [ ] `DEBUG=false` set
- [ ] `CORS_ORIGINS` set to explicit domain(s), NOT `*`
- [ ] HTTPS termination via Nginx or cloud load balancer
- [ ] `uploads/` directory not publicly accessible via web
- [ ] Twilio webhook signature validation active (`TWILIO_AUTH_TOKEN` set)
- [ ] Log rotation configured for access/error logs
