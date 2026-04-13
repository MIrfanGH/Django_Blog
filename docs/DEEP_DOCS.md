<div align="center">

# MyDailyBlog

**A production-grade Django blogging platform — built, deployed, and maintained independently.**

[![Live](https://img.shields.io/badge/Live-mydailyblog.me-brightgreen?style=flat-square)](https://mydailyblog.me)
[![Python](https://img.shields.io/badge/Python-3.12-blue?style=flat-square&logo=python)](https://python.org)
[![Django](https://img.shields.io/badge/Django-5.2-darkgreen?style=flat-square&logo=django)](https://djangoproject.com)
[![AWS](https://img.shields.io/badge/AWS-EC2%20%7C%20S3%20%7C%20RDS%20%7C%20ASG-orange?style=flat-square&logo=amazonaws)](https://aws.amazon.com)

> Django 5 · Celery + Redis · Stripe Webhooks · Groq LLM · AWS EC2/S3/RDS/ASG/ALB/VPC · Nginx · Gunicorn · Cloudflare Full (Strict)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Live Demo](#live-demo)
- [Architecture](#architecture)
  - [High-Level Request Flow](#1-high-level-request-flow)
  - [AWS Infrastructure & VPC](#2-aws-infrastructure--vpc)
  - [Auto Scaling & Golden AMI Strategy](#3-auto-scaling--golden-ami-strategy)
  - [Django App Structure](#4-django-app-structure)
  - [Async Pipeline — Celery + Redis](#5-async-pipeline--celery--redis)
  - [Stripe Payment & Webhook Flow](#6-stripe-payment--webhook-flow)
  - [AI Summarization Flow](#7-ai-summarization-flow)
  - [Redis Caching Strategy](#8-redis-caching-strategy)
- [Tech Stack](#tech-stack)
- [Features](#features)
- [Project Structure](#project-structure)
- [Local Development Setup](#local-development-setup)
- [Environment Variables](#environment-variables)
- [Running Background Services](#running-background-services)
- [AWS Production Deployment](#aws-production-deployment)
- [Nginx Configuration](#nginx-configuration)
- [Database](#database)
- [Static & Media Files](#static--media-files)
- [RBAC — Role-Based Access Control](#rbac--role-based-access-control)
- [Design Decisions & Trade-offs](#design-decisions--trade-offs)
- [Security Practices](#security-practices)
- [Author](#author)

---

## Overview

MyDailyBlog is a **production Mini-SaaS blogging platform** built from scratch as a solo engineering project. Every architectural decision — from Redis cache invalidation via Django signals, to Celery's `transaction.on_commit()` hook for safe async email dispatch, to a Golden AMI pipeline for stateless Auto Scaling — was made intentionally and is documented here.

**What makes this production-grade:**
- Stateless application design enabling horizontal scaling via AWS ASG
- Redis-backed caching with signal-driven invalidation (no stale data)
- Stripe Checkout with server-side session creation and HMAC-verified webhooks
- LLM summarization via Groq Llama 3.3 70B, Redis-cached to avoid redundant API calls
- Celery async pipeline with `transaction.on_commit()` safety for all side effects
- Full AWS stack: Custom VPC (public/private subnets, NAT Gateway, IGW) · EC2 · RDS · S3 · ALB · ASG
- Cloudflare Full (Strict) SSL — HTTPS enforced at every hop

A companion **FastAPI layer** (separate repo) exposes the blog data as a RESTful API with JWT/OAuth2 authentication.

---

## Live Demo

| Resource | URL |
|---|---|
| Live Site | https://mydailyblog.me |
| Django Blog GitHub | https://github.com/MIrfanGH/Django_Blog |
| FastAPI Layer GitHub | https://github.com/MIrfanGH/blog-api |

> **Test Stripe Donation:** Card `4242 4242 4242 4242` · Any future expiry · Any 3-digit CVC · This is test mode — no real charges.

---

## Architecture

### 1. High-Level Request Flow

Cloudflare operates in **Full (Strict)** mode — meaning every hop in this chain is HTTPS. The origin EC2 instances serve a valid Certbot certificate (baked into the Golden AMI), and the ALB terminates HTTPS from Cloudflare before forwarding to Nginx.

```
User (browser)
      │ HTTPS
      ▼
┌─────────────────────────────────────────────┐
│  Cloudflare (Full Strict mode)              │
│  · DNS resolution for mydailyblog.me        │
│  · CDN edge caching (static assets)         │
│  · DDoS mitigation + WAF                   │
│  · Points to ALB DNS name (no Elastic IP)  │
└──────────────────┬──────────────────────────┘
                   │ HTTPS (Cloudflare → origin)
                   ▼
┌─────────────────────────────────────────────┐
│  AWS Application Load Balancer (ALB)        │
│  · Listens on :443                          │
│  · Distributes traffic across EC2 instances │
│  · Health checks on target group           │
└──────────────────┬──────────────────────────┘
                   │ HTTPS → EC2 instance
                   ▼
┌─────────────────────────────────────────────┐
│  Nginx (Reverse Proxy) on EC2               │
│  · SSL cert from Certbot (Let's Encrypt)    │
│    baked into Golden AMI                    │
│  · Proxies to Gunicorn via Unix socket      │
│  · Redirects HTTP :80 → HTTPS :443         │
└──────────────────┬──────────────────────────┘
                   │ Unix socket
                   ▼
┌─────────────────────────────────────────────┐
│  Gunicorn (WSGI server)                     │
│  · 2 sync workers                           │
│  · Managed by systemd (auto-restart)        │
└──────────────────┬──────────────────────────┘
                   │ WSGI
                   ▼
┌─────────────────────────────────────────────┐
│  Django Application                         │
│  ┌──────────┐ ┌──────────┐                 │
│  │  blog    │ │  users   │                 │
│  └──────────┘ └──────────┘                 │
│  ┌──────────┐ ┌──────────┐                 │
│  │ payments │ │summarizer│                 │
│  └──────────┘ └──────────┘                 │
└──────┬─────────────────┬────────────────────┘
       │                 │
┌──────▼──────┐  ┌───────▼──────────────────┐
│ Redis DB 0  │  │ Redis DB 1               │
│ Django Cache│  │ Celery Broker            │
│ (views,     │  │ (task queue)             │
│  summaries) │  └──────────┬───────────────┘
└─────────────┘             │
                    ┌───────▼──────────────────┐
                    │ Celery Workers + Beat    │
                    │ (emails, image resize,   │
                    │  periodic reminders)     │
                    └──────────────────────────┘

External Services:
  AWS RDS (PostgreSQL) · AWS S3 (media) · Groq API (LLM) · Stripe API
```

---

### 2. AWS Infrastructure & VPC

The production environment runs inside a **custom VPC** with full public/private subnet isolation. The RDS database and any private resources live in private subnets — not internet-accessible.

```
┌─────────────────────────────────────────────────────────────────┐
│  AWS Region: ap-south-1 (Mumbai)                                │
│                                                                  │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  Custom VPC                                               │  │
│  │                                                           │  │
│  │  ┌──────────────────────┐  ┌──────────────────────────┐  │  │
│  │  │   Public Subnet      │  │   Private Subnet         │  │  │
│  │  │                      │  │                          │  │  │
│  │  │  ┌────────────────┐  │  │  ┌────────────────────┐  │  │  │
│  │  │  │  ALB           │  │  │  │  AWS RDS           │  │  │  │
│  │  │  │  (entry point) │  │  │  │  PostgreSQL        │  │  │  │
│  │  │  └───────┬────────┘  │  │  │  (not internet-    │  │  │  │
│  │  │          │           │  │  │   accessible)      │  │  │  │
│  │  │  ┌───────▼────────┐  │  │  └────────────────────┘  │  │  │
│  │  │  │  Auto Scaling  │  │  │                          │  │  │
│  │  │  │  Group (ASG)   │  │  │  ┌────────────────────┐  │  │  │
│  │  │  │                │  │  │  │  NAT Gateway       │  │  │  │
│  │  │  │  EC2 #1 ┐      │  │  │  │  (outbound traffic │  │  │  │
│  │  │  │  EC2 #2 ├ ...  │  │  │  │   from private     │  │  │  │
│  │  │  │  EC2 #N ┘      │  │  │  │   subnet)          │  │  │  │
│  │  │  │                │  │  │  └────────────────────┘  │  │  │
│  │  │  │  Each EC2:     │  │  │                          │  │  │
│  │  │  │  Ubuntu 22.04  │  │  └──────────────────────────┘  │  │
│  │  │  │  Nginx         │  │                               │  │  │
│  │  │  │  Gunicorn      │  │  ┌──────────────────────────┐  │  │
│  │  │  │  Celery Worker │  │  │  Internet Gateway (IGW)  │  │  │
│  │  │  │  Redis         │  │  │  (public subnet → WAN)   │  │  │
│  │  │  │  (Golden AMI)  │  │  └──────────────────────────┘  │  │
│  │  │  └────────────────┘  │                               │  │
│  │  └──────────────────────┘  Route Tables:                │  │
│  │                            · Public: 0.0.0.0/0 → IGW   │  │
│  └───────────────────────────────────────────────────────  │  │
│                              · Private: 0.0.0.0/0 → NAT   │  │
│                                                            │  │
│  ┌─────────────────────────────────────────────────────┐   │  │
│  │  AWS S3 Bucket (ap-south-1)                         │   │  │
│  │  Profile images · boto3 + django-storages           │   │  │
│  │  Public-read ACL · 24h cache headers                │   │  │
│  └─────────────────────────────────────────────────────┘   │  │
└─────────────────────────────────────────────────────────────────┘

Security Group Rules:
  ALB:  80 (HTTP) + 443 (HTTPS) from 0.0.0.0/0
  EC2:  Traffic from ALB security group only · SSH :22 restricted
  RDS:  :5432 from EC2 security group only (VPC-internal)
```

---

### 3. Auto Scaling & Golden AMI Strategy

**Why statelessness matters for ASG:** Auto Scaling launches and terminates EC2 instances dynamically. If any application state lives on the instance (sessions in local memory, uploaded files on disk, SSL certs not baked in), new instances start broken or inconsistent. This project achieves statelessness by:

- **Sessions** — stored in Redis (not local memory or SQLite)
- **Media files** — stored on S3 (not EC2 disk)
- **AI summaries** — stored in Redis cache (not local memory or DB tied to one instance)
- **SSL certificate** — baked into the Golden AMI so every new instance is immediately HTTPS-ready

```
Golden AMI Build Process:
─────────────────────────────────────────────────────────────────
1. SSH into a base EC2 instance
   └─ Install all dependencies (Python, Nginx, Redis, Certbot...)
   └─ Clone project, configure .env
   └─ Run: certbot --nginx -d mydailyblog.me
   └─ Configure systemd services (Gunicorn, Celery, Celerybeat)
   └─ Run: collectstatic, migrate

2. Create AMI snapshot from this configured instance
   └─ This becomes the "Golden AMI"

3. Update Launch Template → point to new Golden AMI

4. Update Auto Scaling Group → use updated Launch Template
   └─ New instances launched by ASG are fully configured
   └─ Certificate, app code, and services — all pre-baked

ASG Scaling Policy:
  Scale-out: CPU > 70%  → launch new EC2 from Golden AMI
  Scale-in:  CPU < 30%  → terminate excess instances
  ALB health check: removes unhealthy instances from target group
─────────────────────────────────────────────────────────────────
```

> **Note:** `deploy/gunicorn.service`, `deploy/celery.service`, and `deploy/nginx.service` in this repo contain the exact systemd unit files installed on each EC2 instance during the Golden AMI build.

---

### 4. Django App Structure

Four isolated Django apps, each owning its domain completely.

```
Blog_App/                     ← Project config (settings, urls, celery)
│
├── blog/                     ← Core blogging engine
│   ├── models.py             Post (title, content, content_nature, author FK)
│   ├── views.py              PostListView (Redis cached), PostDetailView (cache_page),
│   │                         PostCreate/Update/Delete (RBAC + ownership check)
│   ├── signals.py            post_save / post_delete → invalidate Redis cache keys
│   ├── tasks.py              post/update/delete email notifications + Beat reminder
│   └── urls.py               / · /post/create/ · /post/<pk>/detail/ · etc.
│
├── users/                    ← Auth, profiles, RBAC
│   ├── models.py             Profile (OneToOne→User, S3 image, role)
│   ├── mixins.py             RoleRequiredMixin → AuthorRequiredMixin
│   ├── views.py              register() · profile() (atomic DB + on_commit tasks)
│   ├── signals.py            post_save → auto-create Profile + welcome email
│   ├── tasks.py              welcome email · profile email · S3 image resize
│   └── urls.py               /users/register/ · /users/login/ · /users/profile/
│
├── payments/                 ← Stripe donation pipeline
│   ├── models.py             Donation (name, email, amount, status: pending→succeeded)
│   ├── views.py              CheckoutSession · Webhook (HMAC-verified) · Success · Cancel
│   ├── tasks.py              send_donation_appreciation_email
│   └── urls.py               /payments/ · /payments/create-donation-session/
│                             /payments/webhooks/stripe/
│
└── summarizer/               ← LLM summarization module
    ├── services.py           generate_blog_summary() → Groq Llama 3.3 70B
    ├── views.py              summarize_post() → Redis check → Groq → cache 1h → redirect
    └── urls.py               /summarize/<post_id>/
```

---

### 5. Async Pipeline — Celery + Redis

All side effects run outside the request-response cycle. `transaction.on_commit()` is used throughout to guarantee tasks fire only after a successful DB commit — preventing orphan tasks if a transaction rolls back.

```
Request arrives (e.g. user registers)
        │
        ▼
┌────────────────────────────┐
│  Django View               │
│  1. Save to DB (atomic)    │
│  2. transaction.on_commit( │
│       task.delay()         │──────────────────────────┐
│     )                      │                          │
│  3. Return response        │                          │
│     immediately            │                          │
└────────────────────────────┘                          │
                                                        ▼
                                           ┌────────────────────────┐
                                           │  Redis DB 1            │
                                           │  Celery Broker         │
                                           │  Task serialized JSON  │
                                           └────────────┬───────────┘
                                                        │
                                                        ▼
                                           ┌────────────────────────┐
                                           │  Celery Worker         │
                                           │  Picks task from queue │
                                           │  Executes (e.g. email) │
                                           │  On fail → retry ×3   │
                                           │  (countdown = 300s)    │
                                           │  Results → Django DB   │
                                           └────────────────────────┘

Task Registry:
────────────────────────────────────────────────────────────────────
App        Task                            Trigger
────────────────────────────────────────────────────────────────────
blog       post_notifying_email            Post created
blog       post_update_notifying_email     Post updated
blog       notify_post_deletion            Post deleted
blog       send_blog_reminder (Beat)       Every 10 days — re-engage
                                           users with no recent posts
users      send_welcome_email              New user registered
users      profile_update_email            Profile saved
users      process_profile_image           New image uploaded →
                                           download S3 → resize
                                           800×800 → re-upload S3
payments   send_donation_appreciation_     Stripe webhook confirmed
           email
────────────────────────────────────────────────────────────────────
```

---

### 6. Stripe Payment & Webhook Flow
The payment system went through a deliberate reliability pass after the initial working implementation. The original code handled the happy path well but was vulnerable to duplicate webhook delivery, missing failure handling, and blind trust of Stripe event types. The current implementation adds two layers of idempotency and explicit failure awareness.

```
User visits /payments/
        │ (STRIPE_PUBLIC_KEY passed to template for Stripe.js)
        ▼
User enters amount → clicks Pay
        │ POST /payments/create-donation-session/
        ▼
┌──────────────────────────────────────────┐
│  CreateDonationCheckoutSession           │
│  1. Parse amount from JSON body          │
│  2. Donation.objects.create(             │
│       status='pending')  ← tracks intent │
│  3. stripe.checkout.Session.create()     │
│     metadata = {donation_id: <id>}       │
│  4. Return {id: session.id}              │
└──────────────────┬───────────────────────┘
                   │ Stripe.js redirectToCheckout
                   ▼
         ┌──────────────────┐
         │  Stripe Hosted   │
         │  Checkout Page   │ ← Collects card, name, email
         └────────┬─────────┘
                  │ Payment processed
                  ▼
         User → /payments/success/ or /payments/cancel/

SIMULTANEOUSLY (server-to-server from Stripe):
         POST /payments/webhooks/stripe/
              │
              ▼
         ── LAYER 0: Signature verification ──────────────────────
         stripe.Webhook.construct_event()
         Verifies HMAC signature → rejects (400) if invalid
         Any unverified request is rejected before DB is touched
              │
              ▼
         ── LAYER 1: Event-level idempotency ─────────────────────
         try:
             ProcessedEvent.objects.create(event_id=event['id'])
         except IntegrityError:
             return HttpResponse(status=200)   # already handled

         Stripe retries the same webhook on network failures.
         The unique constraint on event_id means each Stripe event
         is processed exactly once, regardless of delivery count.
              │
              ▼
         ── on checkout.session.completed ────────────────────────
         Explicit payment_status check:
             if session.get('payment_status') != 'paid':
                 return HttpResponse(status=200)
         checkout.session.completed does not guarantee payment.
         This guard prevents marking a donation as succeeded
         before funds are actually confirmed.
              │
              ▼
         ── LAYER 2: Business-level idempotency ──────────────────
         donation = Donation.objects.get(id=donation_id)
         if donation.status == 'succeeded':
             return HttpResponse(status=200)   # already processed

         Protects against any edge case that bypasses Layer 1.
              │
              ▼
         donation.status = 'succeeded'
         donation.donor_name / donor_email ← from Stripe session
         donation.save()
              │
              ▼
         send_donation_appreciation_email.delay()
              │
              ▼
         return HTTP 200 (always — prevents Stripe retries)

         ── on payment_intent.payment_failed ─────────────────────
         donation.status = 'failed'
         donation.save()
         (pending = abandoned or incomplete; failed = explicit failure)

Key design decisions:

Two-layer idempotency instead of one — event-level deduplication catches Stripe retries; business-level guards catch any edge case that slips through. Either layer alone is incomplete.
Stateless webhook handler — each event is processed as independent. No shared variables, no assumed prior state. Everything needed is fetched fresh from the current event payload.
Explicit payment validation — checkout.session.completed signals that the checkout flow completed, not that payment succeeded. payment_status == 'paid' is verified explicitly.
Failure events handled — payment_intent.payment_failed sets status='failed'. Without this, failed payments remain pending forever and become invisible in reporting.
```

---

### 7. AI Summarization Flow
The summarization system was rebuilt from a simple synchronous view into a layered async pipeline after identifying three production failure modes in the original: request thread blocking, no persistence beyond Redis TTL, and unprotected concurrent stampedes. Eight changes were made. The result follows one principle: generate once, serve many times, regenerate only when the content actually changes.

```
User clicks "Summarize" on a post
        │ GET /summarize/<post_id>/
        ▼
┌───────────────────────────────────────────────┐
│  get_post_summary(post) — service layer       │
│                                               │
│  current_hash = SHA-256(post.content)         │
│  cache_key  = "summary:<id>:<hash>"           │
│  lock_key   = "summary_lock:<id>:<hash>"      │
└──────────────┬────────────────────────────────┘
               │
               ▼
       ┌───────────────┐
       │  Redis check  │── HIT ──► return summary immediately
       └───────┬───────┘
               │ MISS
               ▼
       ┌───────────────────────────────────────┐
       │  DB check                             │
       │  PostSummary.objects.filter(post=post)│
       │  Does content_hash match?             │
       └───────┬───────────────────────────────┘
               │ MATCH → backfill Redis, return
               │ MISMATCH or missing ↓
               ▼
       ┌───────────────────────────────────────┐
       │  Lock check                           │
       │  if not cache.get(lock_key):          │
       │      cache.set(lock_key, True, 60s)   │
       │      generate_post_summary_task.delay │
       └───────┬───────────────────────────────┘
               │
               ▼
       return None  ← view shows "generating..." message
       (user refreshes; by then Celery has written to DB + cache)

─────────────────────────────────────────────────────────────
BACKGROUND: generate_post_summary_task (Celery)
─────────────────────────────────────────────────────────────
        │
        ▼
┌───────────────────────────────────────────────┐
│  generate_post_summary(content)               │
│  · Groq client, Llama 3.3 70B                │
│  · temperature=0.3 (factual, low randomness) │
│  · timeout=10s hard cap on API call          │
└──────────────┬────────────────────────────────┘
               │ success
               ▼
  PostSummary.objects.update_or_create(
      post_id=post_id,
      defaults={
          summary, content_hash,
          generation_time_ms, generation_model
      }
  )   ← idempotent write; safe to retry

  cache.set(cache_key, summary, 3600)
  cache.delete(lock_key)          ← release immediately on success
               │
               │ on failure
               ▼
  raise self.retry(
      exc=e,
      countdown=2 ** self.request.retries * 5   # 5s → 10s → 20s
  )
  finally:
      if self.request.retries >= self.max_retries:
          cache.delete(lock_key)  ← always release on final failure
                                    (prevents 60s stale lock blocking
                                     all retries after a worker crash)
─────────────────────────────────────────────────────────────
```
Content-addressable invalidation :
— the hash is what makes "regenerate only when content changes" precise. No manual flags, no timestamp comparison, no TTL guessing. If the content hasn't changed, the hash hasn't changed, and the cached summary is still valid.
Why update_or_create for DB writes — the Celery task can be retried up to 3 times. update_or_create makes the DB write idempotent: running it twice for the same post_id updates in place rather than creating duplicates.
Why lock release in finally, not just on success — a worker crash between task execution and lock expiry leaves the lock alive for up to 60 seconds. During that window, all concurrent requests silently skip generation and return None. The finally block guarantees the lock is always released — either immediately on success, or on the final retry failure.


---

### 8. Redis Caching Strategy

```
Redis DB 0 — Django Cache
──────────────────────────────────────────────────────────────────
Cache Key              TTL      Set by                Invalidated by
──────────────────────────────────────────────────────────────────
post_list_view         3600s    PostListView           post_save signal
                                get_queryset()         post_delete signal

user_posts_<username>  1800s    SameUserPostListView   post_save signal
                                get_queryset()         post_delete signal

post_detail_<pk>       3600s    PostDetailView         post_save signal
                                (cache_page decorator) post_delete signal

post_summary_<id>      3600s    summarize_post()       TTL expiry only
──────────────────────────────────────────────────────────────────

Redis DB 1 — Celery Broker
  Task messages: JSON-serialized, consumed by Celery worker
  Results: stored in Django default DB (django-celery-results)

Cache Invalidation:
  blog/signals.py → invalidate_post_cache(post)
  Called by @receiver(post_save) and @receiver(post_delete)
  Deletes: post_list_view, user_posts_<username>, post_detail_<pk>
  Result: next request hits DB, repopulates cache — no stale data served

```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Web Framework | Django 5.2 | Core app, ORM, admin, auth |
| App Server | Gunicorn 23 | WSGI production server |
| Reverse Proxy | Nginx | SSL termination, Unix socket proxy |
| Task Queue | Celery 5.5 | Async background tasks |
| Message Broker / Cache | Redis 7 | Celery broker (DB1) + Django cache (DB0) |
| Database (dev) | SQLite | Local development |
| Database (prod) | PostgreSQL via AWS RDS | Production persistence |
| Object Storage | AWS S3 + boto3 + django-storages | User media files |
| Static Files | Whitenoise | Efficient static file serving |
| Payments | Stripe API + Webhooks | Donation checkout pipeline |
| AI / LLM | Groq API (Llama 3.3 70B) | Blog post summarization |
| CDN / DNS | Cloudflare (Full Strict) | Edge caching, DDoS, HTTPS everywhere |
| Infrastructure | AWS EC2, RDS, S3, VPC, ASG, ALB | Full cloud production stack |
| Process Management | systemd | Gunicorn, Celery, Celerybeat lifecycle |
| Image Processing | Pillow | Profile image resize + compress (via Celery) |
| Forms | django-crispy-forms + Bootstrap 5 | Styled form rendering |

---

## Features

### Authentication & User Management

- Registration with email, auto-profile creation via Django `post_save` signal
- Login / logout via Django's built-in auth views
- Password reset via email (4-step tokenized flow)
- Profile update (username, email, avatar) with atomic `transaction.atomic()` wrapping both User and Profile saves
- Profile image uploaded to S3, then asynchronously downloaded → resized (max 800×800, LANCZOS) → re-uploaded as JPEG (85% quality) via Celery — all without blocking the response
- Welcome email dispatched via `transaction.on_commit()` — fires only after successful DB commit

### Role-Based Access Control (RBAC)

| Role | Permissions |
|---|---|
| `Reader` (default) | View posts, donate, request AI summaries |
| `Author` | All Reader permissions + create, update, delete own posts |
| `Admin` | Full access |

### Blog CRUD

- Create, Read, Update, Delete posts (title, content type, content)
- `select_related('author')` on all list queries — prevents N+1 DB hits
- Pagination: 4 posts per page
- Per-user post feed at `/user/<username>/posts/`
- Redis-cached home feed (1h TTL), invalidated instantly on any post change via signals
- Async email notification on every post action (create / update / delete)

### AI Summarization

-AI Summarization — one-click Groq LLM summary per post; original content never modified
⚡ Non-blocking pipeline — LLM call runs in a background Celery task; view returns immediately
🗄️ Cache-aside with DB fallback — Redis is the hot path, PostgreSQL is the source of truth; summaries survive cache restarts and evictions
🔒 Stampede protection — distributed Redis lock ensures a single Groq call per unique content hash, regardless of concurrent requests
🔁 Content-addressable freshness — SHA-256 hash of post content stored alongside every summary; hash mismatch triggers automatic regeneration, no manual flags needed
📉 Retry with exponential backoff — 3 retries at 5s / 10s / 20s; lock released in finally block so a worker crash never silently blocks future attempts
⏱️ Hard timeout — 10s cap on the LLM call prevents Celery workers hanging indefinitely
🚦 Per-user rate limiting — 5 requests per 60s (keyed by user ID or IP for anonymous users) to protect API quota

### Stripe Donations

💳 Stripe Donations — server-side checkout session creation; no card data touches the backend
🛡️ HMAC-verified webhooks — stripe.Webhook.construct_event() signature check before any DB write
🔂 Two-layer idempotency — event-level deduplication via ProcessedEvent (unique constraint on Stripe event ID catches duplicate deliveries at DB layer); business-level guard (if donation.status == 'succeeded': return 200) prevents reprocessing even if the first layer is bypassed
✅ Explicit payment validation — payment_status == 'paid' verified before marking success; checkout.session.completed alone is not trusted blindly
❌ Failure handling — payment_intent.payment_failed events handled explicitly; failed status is set in DB rather than leaving donations permanently pending
📬 State machine — Donation record created as pending on checkout creation; transitions to succeeded or failed based on webhook events only
🔄 Stateless webhook handler — each event is treated as independent; no shared variables, no assumed prior state, all data fetched fresh from the current event payload
- Test mode active (card `4242 4242 4242 4242`)

### Periodic Tasks (Celery Beat)

- Every 10 days: identifies users with no posts in 10 days → sends re-engagement email
- All Celery tasks: `max_retries=3`, `countdown=300s` (5-minute retry backoff)

---

## Project Structure

```
Blog_Application/
├── Blog_App/                 ← Django project config
│   ├── settings.py           Env-driven settings, dev/prod DB split
│   ├── urls.py               Root URL routing
│   ├── celery.py             Celery app init + autodiscover_tasks
│   ├── wsgi.py
│   └── asgi.py
├── blog/                     ← Blog app (posts, caching, signals)
├── users/                    ← Auth, profiles, RBAC, image processing
├── payments/                 ← Stripe donation pipeline
├── summarizer/               ← Groq LLM summarization
├── deploy/                   ← systemd service files for EC2
│   ├── gunicorn.service      Gunicorn unit file (used in Golden AMI build)
│   ├── celery.service        Celery worker + Beat unit files
│   └── nginx.service         Nginx unit file
├── docs/                     ← Supplementary architecture docs
│   ├── DEPLOYMENT_AWS.md
│   ├── SYSTEM_DESIGN.md
│   └── AI_SUMMARIZATION.md
├── static/                   ← Source static files
├── staticfiles/              ← collectstatic output (served by Whitenoise)
├── manage.py
├── requirements.txt
├── Procfile
└── .env                      ← Local secrets (never committed)
```

---

## Local Development Setup

### Prerequisites

Install the following before starting:

- **Python 3.12+** — [python.org](https://python.org)
- **Redis** — used for Django cache and Celery broker
  - macOS: `brew install redis`
  - Ubuntu: `sudo apt install redis-server`
- **Git** — [git-scm.com](https://git-scm.com)
- **pip** — comes with Python
- A **Gmail account** with an [App Password](https://support.google.com/accounts/answer/185833) configured for SMTP
- A **Stripe account** (free) with test API keys — [stripe.com](https://stripe.com)
- A **Groq API key** (free tier) for LLM summarization — [console.groq.com](https://console.groq.com)
- **AWS account** with an S3 bucket and IAM user credentials (for media uploads)

> For local dev, SQLite is used by default — no PostgreSQL installation needed.

---

### Setup Steps

**1. Clone the repository**

```bash
git clone https://github.com/MIrfanGH/Django_Blog.git
cd Django_Blog
```

**2. Create and activate a virtual environment**

```bash
python -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

This installs Django, Celery, Redis client, Stripe SDK, Groq SDK, Pillow, boto3, and all other dependencies.

**4. Configure environment variables**

```bash
cp .env.example .env
# Fill in all values — see Environment Variables section below
```

**5. Apply migrations**

```bash
python manage.py migrate
```

**6. Collect static files**

```bash
python manage.py collectstatic --noinput
```

**7. Create a superuser**

```bash
python manage.py createsuperuser
```

**8. Start Redis** (required — without it, caching and Celery both fail)

```bash
# macOS
brew services start redis

# Ubuntu
sudo systemctl start redis-server

# Verify
redis-cli ping   # should return PONG
```

**9. Start Celery worker** (new terminal) — required for async emails and image processing

```bash
celery -A Blog_App worker --loglevel=info --concurrency=1
```

**10. Start Celery Beat** (new terminal) — required for periodic re-engagement emails

```bash
celery -A Blog_App beat --loglevel=info
```

**11. Run the development server**

```bash
python manage.py runserver
```

Visit `http://127.0.0.1:8000/`

> You need at least **4 terminals** running simultaneously in local dev: Django, Redis, Celery Worker, Celery Beat.

---

## Environment Variables

Create a `.env` file in the project root. **Never commit this file** — it is in `.gitignore`.

```env
# Django Core
SECRET_KEY=your-django-secret-key-here
DEBUG=True
DJANGO_ENV=development        # Change to 'production' to switch DB to PostgreSQL

# Database — only used when DJANGO_ENV=production
DB_NAME=your_db_name
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_HOST=your-rds-endpoint.rds.amazonaws.com
DB_PORT=5432

# Email (Gmail SMTP — use an App Password, not your Gmail password)
HOST_EMAIL=your-email@gmail.com
HOST_EMAIL_PASSWORD=your-16-char-app-password

# AWS S3 (media file storage)
AWS_ACCESS_KEY_ID=AKIA...
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_STORAGE_BUCKET_NAME=your-bucket-name

# Stripe (use test keys locally)
STRIPE_PUBLIC_KEY=pk_test_...
STRIPE_SECRET_KEY=sk_test_...
STRIPE_WEBHOOK_SECRET_KEY=whsec_...

# Groq LLM API
GROQ_SUMMARIZATION_KEY=gsk_...
```

---

## Running Background Services

### Local Development

```bash
# Terminal 1 — Django
python manage.py runserver

# Terminal 2 — Celery Worker (processes all async tasks)
celery -A Blog_App worker --loglevel=info --concurrency=1

# Terminal 3 — Celery Beat (periodic task scheduler)
celery -A Blog_App beat --loglevel=info

# Terminal 4 — Redis (if not running as a system service)
redis-server
```

### Production (systemd)

The `deploy/` folder contains the exact systemd unit files installed during the Golden AMI build. Enable and start each service:

```bash
sudo systemctl enable --now gunicorn
sudo systemctl enable --now celery
sudo systemctl enable --now celerybeat
sudo systemctl enable --now redis-server
sudo systemctl enable --now nginx
```

Check all at once:

```bash
sudo systemctl status gunicorn celery celerybeat redis-server nginx
```

View Celery logs:

```bash
tail -f /home/ubuntu/Django_Blog/logs/celery.log
tail -f /home/ubuntu/Django_Blog/logs/celerybeat.log
```

---

## AWS Production Deployment

This is the exact sequence used to build and deploy the live environment.

### 1. Launch a Base EC2 Instance

- AMI: Ubuntu 22.04 LTS
- Instance type: `t2.small`
- Storage: 20 GB SSD
- Place in the **public subnet** of your custom VPC
- Security Group: SSH (22) restricted, HTTP (80) and HTTPS (443) open

### 2. Connect and Install Dependencies

```bash
ssh -i blogkeypair2.pem ubuntu@<instance-public-ip>

sudo apt update && sudo apt upgrade -y
sudo apt install python3-pip python3-venv nginx redis-server postgresql-client certbot python3-certbot-nginx -y
```

### 3. Clone and Configure the Project

```bash
cd /home/ubuntu
git clone https://github.com/MIrfanGH/Django_Blog.git
cd Django_Blog

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set all production values including DJANGO_ENV=production
nano .env

python manage.py migrate
python manage.py collectstatic --noinput
mkdir -p logs
```

### 4. Install systemd Services

Copy the service files from `deploy/` to systemd:

```bash
sudo cp deploy/gunicorn.service /etc/systemd/system/
sudo cp deploy/celery.service /etc/systemd/system/
# (repeat for celerybeat and nginx configs)

sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn celery celerybeat
```

### 5. Configure Nginx and Obtain SSL Certificate

```bash
sudo nano /etc/nginx/sites-available/Blog_App
# Paste Nginx config (see Nginx Configuration section)

sudo ln -s /etc/nginx/sites-available/Blog_App /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl restart nginx

# Obtain Let's Encrypt certificate (Certbot configures Nginx automatically)
sudo certbot --nginx -d mydailyblog.me -d www.mydailyblog.me
```

### 6. Create the Golden AMI

Once the instance is fully configured and all services are running:

1. In AWS Console → EC2 → select the instance → **Actions → Image → Create Image**
2. Name it (e.g. `mydailyblog-golden-ami-v1`)
3. Wait for AMI to be available

### 7. Update Launch Template and ASG

1. EC2 → Launch Templates → create new version pointing to the Golden AMI
2. Auto Scaling Group → edit → update to use the new Launch Template version
3. New instances launched by the ASG will be fully configured with cert, app, and all services pre-baked

### 8. Set Up ALB

1. Create Application Load Balancer in the public subnet
2. Configure listener on :443 (HTTPS) — the ALB receives HTTPS from Cloudflare
3. Register the EC2 target group
4. Point Cloudflare DNS to the **ALB DNS name** (not an Elastic IP)

### 9. Configure Stripe Webhook

In the Stripe dashboard, add webhook endpoint:
```
https://mydailyblog.me/payments/webhooks/stripe/
```
Event: `checkout.session.completed`
Copy the signing secret → `STRIPE_WEBHOOK_SECRET_KEY` in `.env`

---

## Nginx Configuration

The live config installed via Certbot on the EC2 Golden AMI:

```nginx
# HTTP → HTTPS redirect
server {
    listen 80;
    server_name mydailyblog.me www.mydailyblog.me;
    return 301 https://$host$request_uri;
}

# HTTPS — main server block
server {
    listen 443 ssl;
    server_name mydailyblog.me www.mydailyblog.me;

    # Certbot-managed Let's Encrypt certificates (baked into Golden AMI)
    ssl_certificate     /etc/letsencrypt/live/mydailyblog.me/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/mydailyblog.me/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Proxy all requests to Gunicorn via Unix socket
    location / {
        proxy_pass http://unix:/run/gunicorn/gunicorn.sock;
        include proxy_params;
    }
}
```

**Why Unix socket over TCP?** Both Nginx and Gunicorn run on the same EC2 instance. A Unix domain socket eliminates TCP handshake overhead and avoids binding a port, reducing attack surface.

**Why Cloudflare in front of ALB?** Cloudflare absorbs DDoS traffic at the edge, caches static assets globally, and provides the public-facing SSL. With Full (Strict) mode, Cloudflare also validates the origin certificate — meaning the entire chain (browser → Cloudflare → ALB → Nginx) is encrypted.

---

## Database

| Environment | Database | Activated by |
|---|---|---|
| Development | SQLite (`db.sqlite3`) | Default (`DJANGO_ENV` not set) |
| Production | PostgreSQL (AWS RDS, private subnet) | `DJANGO_ENV=production` |

```python
# settings.py
if os.getenv('DJANGO_ENV', 'development') == 'production':
    DATABASES = { 'default': { 'ENGINE': 'django.db.backends.postgresql_psycopg2', ... } }
else:
    DATABASES = { 'default': { 'ENGINE': 'django.db.backends.sqlite3', ... } }
```

The RDS instance is in a **private subnet** — accessible only from EC2 instances in the same VPC security group. It has no public IP.

---

## Static & Media Files

| Type | Development | Production |
|---|---|---|
| Static files | Django `runserver` | Whitenoise (compressed, fingerprinted) |
| Media files | Local filesystem | AWS S3 (`ap-south-1`) via boto3 |

**Whitenoise for static, S3 for media** — static files are deterministic build artifacts that Whitenoise compresses and fingerprints at deploy time. Media files are user-uploaded blobs that belong on object storage. S3 scales independently of the application server and is accessible from all EC2 instances behind the ALB — essential for stateless ASG operation.

**Profile image processing pipeline (via Celery):**
1. User uploads image → saved to S3 immediately
2. `transaction.on_commit()` → dispatches `process_profile_image` Celery task
3. Celery downloads image from S3 → converts to RGB → resizes (max 800×800 LANCZOS) → saves as JPEG (85% quality) → re-uploads to S3

---

## RBAC — Role-Based Access Control

```python
# users/mixins.py
class RoleRequiredMixin(UserPassesTestMixin):
    required_role = None
    def test_func(self):
        return (self.request.user.is_authenticated and
                self.request.user.profile.role == self.required_role)

class AuthorRequiredMixin(RoleRequiredMixin):
    required_role = 'Author'
```

Applied to views with intentional MRO ordering:

```python
class PostCreateView(AuthorRequiredMixin, LoginRequiredMixin, CreateView):
    ...

class PostUpdateView(AuthorRequiredMixin, LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    def test_func(self):
        post = self.get_object()
        # Both role check AND ownership must pass
        return super().test_func() and self.request.user == post.author
```

`LoginRequiredMixin` is always listed before RBAC mixins in MRO so unauthenticated users are redirected to login before the role check fires. New users default to `Reader`. Role upgrades are done via the Django admin panel.

---

## Design Decisions & Trade-offs

**Why Redis for AI summaries, not sessions?**
The original implementation stored summaries in Django sessions. When the ASG scales horizontally, session data stored locally on one EC2 is invisible to other instances behind the ALB — a user hitting a different instance gets no summary. Redis is shared infrastructure across all instances, making summaries available regardless of which EC2 serves the request.

**Why synchronous AI calls, not Celery?**
Groq's inference typically responds in under 2 seconds — fast enough to stay in the request cycle. The UX is immediate: click "Summarize", see the result. If summarization becomes batch-based, personalized, or slower, the `services.py` function can be wrapped in a Celery task with no changes to the business logic.

**Why `transaction.on_commit()` for Celery tasks?**
Without it, a task can be dispatched before the DB transaction commits — resulting in a welcome email sent for a user registration that then rolls back. `on_commit()` guarantees tasks only fire on successful commit. No orphan side effects.

**Why Whitenoise instead of S3 for static files?**
Static files are identical for every user and change only on deploy. Whitenoise compresses and fingerprints them at startup, serving them with long Cache-Control headers. S3 adds a cross-service roundtrip and bucket configuration for no benefit at this scale. S3 is the right tool for dynamic, user-generated blobs.

**Why Unix socket for Gunicorn?**
Both Nginx and Gunicorn are on the same machine. A Unix socket eliminates TCP overhead and avoids occupying a port.

**Why Golden AMI instead of user data scripts?**
User data scripts run on every instance launch — installing packages, running `git clone`, applying migrations. This adds 3–5 minutes to cold start time and introduces network-dependency failures at scale. A Golden AMI bakes everything in at AMI creation time. New instances are ready in seconds.

---

## Security Practices

- `DEBUG=False` in production — enforced via `DJANGO_ENV` env var
- All secrets in `.env` via `python-dotenv` — never hardcoded
- CSRF protection globally via `CsrfViewMiddleware`; `CSRF_TRUSTED_ORIGINS` set to exact domains
- HTTPS enforced end-to-end — Cloudflare Full (Strict) mode; Nginx redirects HTTP → HTTPS
- Stripe webhook HMAC signature verified before any DB write
- AWS IAM: least-privilege — S3 access key scoped to single bucket only
- RDS in private subnet — no public IP, VPC-internal access only
- SSH access restricted (key-pair auth, restricted IP)
- Celery task results auto-expire after 1 hour (`CELERY_RESULT_EXPIRES = 3600`)

---

## Author

**Muhammad Irfan** — Python Backend Developer
Django · FastAPI · AWS · Celery · Redis · Stripe · LLM Integration

- Email: 801.mirfan@gmail.com
- Live: [mydailyblog.me](https://mydailyblog.me)
- GitHub: [github.com/MIrfanGH](https://github.com/MIrfanGH)
- LinkedIn: [/muhammad-irfan891](https://www.linkedin.com/in/muhammad-irfan891)
- Location: Mumbai, India

---

<div align="center">
If you found this useful, please give it a ⭐ on GitHub.
</div>