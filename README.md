

# MyDailyBlog

**Production-grade Django blogging platform — built and deployed independently end-to-end.**

---

## 🚀 What This Is

A Mini-SaaS blog platform built from scratch — not a tutorial clone. Features Stripe donations, LLM-powered post summarization, async email pipelines, Redis caching, RBAC, and a full AWS production deployment with Auto Scaling.

**Live:** https://mydailyblog.me · **GitHub:** https://github.com/MIrfanGH/Django_Blog

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Django 5.2, Python 3.12, Gunicorn |
| Async | Celery 5.5 + Redis (broker + cache) |
| Database | PostgreSQL (AWS RDS in prod) · SQLite (dev) |
| Storage | AWS S3 + boto3 + django-storages |
| Payments | Stripe Checkout API + Webhooks |
| AI / LLM | Groq API — Llama 3.3 70B |
| Infrastructure | AWS EC2, RDS, S3, VPC, ASG, ALB |
| Reverse Proxy | Nginx + Gunicorn (Unix socket) |
| CDN / DNS | Cloudflare Full (Strict) SSL |
| Static Files | Whitenoise |

---

## ✨ Key Features

- 🔐 **RBAC** — Reader / Author / Admin roles enforced via custom Django mixins

- 💳 **Stripe Donations** — server-side checkout session, HMAC-verified webhooks, two-layer idempotency (event-level + business-level), explicit failure handling

- 🤖 **AI Summarization** — async Groq LLM summary (Celery task), cache-aside with DB fallback, stampede protection via        distributed locking, content-hash freshness detection

- ⚙️ **Async Emails** — Celery handles all notifications (registration, post events, donations, periodic re-engagement); `transaction.on_commit()` used throughout to prevent orphan tasks
- ⚡ **Redis Caching** — post list, per-user feeds, and detail pages cached with signal-driven invalidation on every create/update/delete
- ☁️ **Stateless Design** — sessions, media, AI summaries, and SSL certs all live off-instance, enabling true horizontal scaling behind the ALB

---

## 🏗️ Architecture (Quick View)

```
User → Cloudflare (CDN + DDoS) → ALB → Nginx → Gunicorn → Django
                                                        ↓
                                          Redis (cache DB0 + broker DB1)
                                                        ↓
                                              Celery Workers + Beat
                                                        ↓
                              AWS RDS · AWS S3 · Groq API · Stripe API
```

**AWS Stack:** Custom VPC · Public + Private subnets · Internet Gateway · NAT Gateway · Route Tables · ALB · Auto Scaling Group · EC2 (Ubuntu 22.04) · RDS (private subnet) · S3

**Golden AMI pipeline:** Configure EC2 → install Certbot cert → bake AMI → update Launch Template → ASG launches pre-configured instances in seconds.

---

## 📁 Project Structure

```
Blog_Application/
├── Blog_App/        ← Django config (settings, urls, celery)
├── blog/            ← Post CRUD, Redis caching, signals, email tasks
├── users/           ← Auth, RBAC mixins, profile, S3 image processing
├── payments/        ← Stripe checkout, webhook handler, donation model
├── summarizer/      ← Groq LLM service, Redis-cached summary view
└── docs/            ← Full architecture deep-dive (see DEEP_DOCS.md)
```

---

## ⚡ Quick Start (Local)

```bash
git clone https://github.com/MIrfanGH/Django_Blog.git && cd Django_Blog
python -m venv venv

# macOS / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
# Create .env and fill in your keys
python manage.py migrate
python manage.py runserver  # also start Redis + Celery worker + Celery beat
```

> Requires: Python 3.12+, Redis, and API keys for Stripe, Groq, and AWS S3. See [`docs/DEEP_DOCS.md`](docs/DEEP_DOCS.md) for the full setup guide.

---

## 💳 Test the Donation Flow

Visit `/payments/` and use Stripe test card: `4242 4242 4242 4242` · any future expiry · any CVC.

---

## 📖 Deep Documentation

For full architecture diagrams, AWS deployment steps, Golden AMI walkthrough, Nginx config, caching strategy, design decisions, and more — see [`docs/DEEP_DOCS.md`](docs/DEEP_DOCS.md).

---

## 👤 Author

**Muhammad Irfan** — Python Backend Developer · Django · FastAPI · AWS · Celery · Stripe · LLM

[mydailyblog.me](https://mydailyblog.me) · [github.com/MIrfanGH](https://github.com/MIrfanGH) · [LinkedIn](https://www.linkedin.com/in/muhammad-irfan891) · 801.mirfan@gmail.com · Mumbai, India