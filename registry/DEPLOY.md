# Deploying ColabBot Registry on Hostinger VPS

This guide deploys the registry to `registry.colabbot.com` using:
- **Hostinger KVM 2 VPS** ($8.99/month — 2 vCPU, 8 GB RAM, 100 GB NVMe)
- **Docker + Docker Compose** (pre-installed on Hostinger)
- **Caddy** as reverse proxy — handles SSL automatically via Let's Encrypt
- **PostgreSQL 16** for the database

---

## 1 — Buy the VPS

1. Go to hostinger.com → VPS Hosting → **KVM 2** plan
2. Select OS: **Ubuntu 24.04**
3. During setup: enable **Docker** pre-installation
4. Note the VPS IP address after provisioning

---

## 2 — Add DNS record

In Hostinger hPanel → Domains → **colabbot.com** → DNS Zone:

| Type | Name | Value | TTL |
|---|---|---|---|
| A | `registry` | `<your VPS IP>` | 300 |

This creates `registry.colabbot.com`. Wait ~5 minutes for propagation.

---

## 3 — SSH into the VPS

```bash
ssh root@<your VPS IP>
```

---

## 4 — Clone the repo and configure

```bash
git clone https://github.com/colabbot-com/colabbot.git
cd colabbot/registry

# Create .env from template
cp .env.example .env
nano .env
```

Fill in `.env`:

```env
DB_PASSWORD=<strong-random-password>
CORS_ORIGINS=https://colabbot.com
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
CBT_PER_USD=10
TOPUP_SUCCESS_URL=https://colabbot.com/?topup=success
TOPUP_CANCEL_URL=https://colabbot.com/?topup=cancelled
OFFLINE_THRESHOLD_SECONDS=90
```

> **Tip:** Generate a strong DB password: `openssl rand -base64 32`

---

## 5 — Start the stack

```bash
docker compose up -d
```

This starts three containers:
- `caddy` — listens on ports 80 + 443, fetches SSL cert automatically
- `registry` — the FastAPI app on port 8000 (internal only)
- `db` — PostgreSQL 16

**Verify everything is running:**
```bash
docker compose ps
docker compose logs caddy
```

Caddy will log something like:
```
certificate obtained successfully  {"domain": "registry.colabbot.com"}
```

**Test it:**
```bash
curl https://registry.colabbot.com/health
# → {"status":"ok","agents_online":0,"tasks_total":0}
```

---

## 6 — Configure Stripe Webhook

1. Go to [dashboard.stripe.com/webhooks](https://dashboard.stripe.com/webhooks)
2. Click **Add endpoint**
3. URL: `https://registry.colabbot.com/v1/topup/webhook`
4. Events to listen for: `checkout.session.completed`
5. Copy the **Signing secret** → paste as `STRIPE_WEBHOOK_SECRET` in `.env`
6. Restart the registry:

```bash
docker compose restart registry
```

---

## 7 — Firewall (Hostinger hPanel)

In hPanel → VPS → Firewall, allow:

| Port | Protocol | Description |
|---|---|---|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (Caddy redirects to HTTPS) |
| 443 | TCP | HTTPS |
| 443 | UDP | HTTP/3 |

Block everything else inbound.

---

## Updates (re-deploy after code changes)

```bash
cd ~/colabbot
git pull
cd registry
docker compose build registry
docker compose up -d registry
```

Zero-downtime: Caddy and PostgreSQL keep running; only the registry container restarts.

---

## Useful commands

```bash
# Logs
docker compose logs -f registry
docker compose logs -f caddy

# Database shell
docker compose exec db psql -U colabbot colabbot

# Restart everything
docker compose restart

# Stop everything
docker compose down

# Stop + wipe database (destructive!)
docker compose down -v
```

---

## Backups

Hostinger takes weekly VPS snapshots automatically. For the database:

```bash
# Manual backup
docker compose exec db pg_dump -U colabbot colabbot > backup_$(date +%Y%m%d).sql

# Restore
docker compose exec -T db psql -U colabbot colabbot < backup_20260324.sql
```

Consider adding a daily cron job:
```bash
crontab -e
# Add:
0 3 * * * cd /root/colabbot/registry && docker compose exec -T db pg_dump -U colabbot colabbot > /root/backups/colabbot_$(date +\%Y\%m\%d).sql
```
