# Orders & Settlements

A small web application for raising customer orders with line items, recording full or
partial payments against them, and tracking what is still owed.

**Stack:** Django 6.1 + Django REST Framework (API) · PostgreSQL · Next.js 16 (App Router,
TypeScript, MUI v7 + React Hook Form/Yup) · JWT auth held in httpOnly cookies.

**Live URL:** _not yet deployed — see [Deployment](#deployment)._

---

## Contents

- [Quick start](#quick-start)
- [Running the tests](#running-the-tests)
- [The sample scenario](#the-sample-scenario)
- [Architecture](#architecture)
- [API overview](#api-overview)
- [Status derivation rules](#status-derivation-rules)
- [Edge cases](#edge-cases)
- [Decisions and rationale](#decisions-and-rationale)
- [Concurrency](#concurrency)
- [Assumptions and tradeoffs](#assumptions-and-tradeoffs)
- [What I would do before production](#what-i-would-do-before-production)
- [Deployment](#deployment)

---

## Quick start

**Prerequisites:** Python 3.12+ and Node.js 20+. Docker is optional (see the database note).

### 1. Backend

```bash
cd backend

python -m venv .venv
# macOS / Linux
source .venv/bin/activate
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

pip install -r requirements-dev.txt
cp .env.example .env          # set DATABASE_URL to your Postgres instance

docker compose up -d
python manage.py migrate
python manage.py seed_demo    # demo@example.com / demo-password-123
python manage.py runserver 127.0.0.1:8000
```

The API is now on <http://127.0.0.1:8000>. `GET /healthz/` should return `{"status": "ok"}`.

**Database.** Postgres only — `DATABASE_URL` is required and the app fails fast at startup if
it is unset. Row-level locking (`SELECT ... FOR UPDATE`, see [Concurrency](#concurrency)) is
load-bearing for the overpayment/overrefund invariant, so no other backend is supported.

### 2. Frontend

```bash
cd frontend
npm install
cp .env.example .env.local    # API_BASE_URL=http://127.0.0.1:8000
npm run dev
```

Open <http://localhost:3000> and log in as `demo@example.com` / `demo-password-123`.

### 3. Seed data

`python manage.py seed_demo` builds six orders that between them cover every status and both
documented edge cases — an order that was overdue and has since been paid in full, and an
order reopened by a refund. Re-running it rebuilds the demo user's data from scratch.

---

## Running the tests

```bash
# backend  — 91 passing
cd backend && pytest -v

# frontend — typecheck, lint, unit tests
cd frontend && npm run typecheck && npm run lint && npm test
```

The backend suite covers the three areas the brief calls out, plus the ones that turned out
to matter:

| Area | File |
|---|---|
| Line item math, decimal quantisation, total computation | `tests/test_money_and_totals.py` |
| Status derivation matrix, precedence, SQL↔Python parity | `tests/test_status_derivation.py` |
| Payment allocation and over-payment rejection | `tests/test_payments.py` |
| Refunds and over-refund rejection | `tests/test_refunds.py` |
| Per-user isolation, auth, 404-not-403 | `tests/test_tenancy_and_auth.py` |
| Order CRUD, edit locking, audit log, CSV export, summary | `tests/test_orders_api.py` |
| Simultaneous payments, transactional rollback | `tests/test_concurrency.py` |

The two-threads-one-order race in `test_concurrency.py` exercises row-level locking directly
against Postgres.

---

## The sample scenario

The flow from the brief, verified end to end against the running API:

```
1. Create order: 2 × $500, due in 7 days
   -> id=7  total=1000.00  status=pending  amount_due=1000.00

2. POST payment 400.00
   -> status=partially_paid  amount_paid=400.00  amount_due=600.00

3. POST payment 600.00
   -> status=paid  amount_paid=1000.00  amount_due=0.00

4. POST payment 1.00
   -> HTTP 400
   {"error":{"code":"OVERPAYMENT",
             "message":"This order is already paid in full ($1,000.00), so a payment
                        of $1.00 cannot be recorded.",
             "details":{"field":"amount","order_total":"1000.00","amount_paid":"1000.00",
                        "max_allowed":"0.00","attempted":"1.00"}}}
```

Attempting $700 when $600 is outstanding gives the more useful variant, which is what the UI
turns into a one-click fix:

```
"A payment of $700.00 would exceed the amount due on this order.
 The most you can record is $600.00."          max_allowed: "600.00"
```

The same scenario is asserted as a test: `test_the_assignment_sample_scenario`.

---

## Architecture

```
backend/
  config/            settings (env-driven), urls, wsgi/asgi
  accounts/          custom email-as-username User, JWT auth endpoints
  orders/
    models.py        Order, LineItem, Payment, Refund, AuditLog + DB constraints
    money.py         Decimal helpers — the only place rounding happens
    selectors.py     read side: status derivation (Python + SQL), tenancy filter
    services.py      write side: transactional, row-locking business operations
    serializers.py   I/O shapes
    views.py         thin viewsets + summary endpoint
    exceptions.py    the single error envelope
    export.py        streaming CSV
  tests/
frontend/
  src/proxy.ts       route guard + proactive token refresh (Next 16 "Proxy")
  src/lib/           api client, server actions, session/token custody, money
  src/schemas/       Yup validation schemas, one per form
  src/providers/     MUI theme provider
  src/app/           dashboard, order create, order detail, auth pages
  src/components/    MUI-based UI, forms wired up with React Hook Form
docker-compose.yml   Postgres for local development
```

Three conventions carry most of the weight:

**Reads go through `selectors.py`, writes go through `services.py`.** Views are thin. Every
read starts from `order_queryset(user)`, which applies both the ownership filter and the
status annotation, so a nested route cannot accidentally skip the tenancy check. Every write
is a service function that owns its own transaction and business rules, so "record a payment"
means the same thing whether it is called from the API, a management command, or a shell.

**The browser never talks to Django.** The Next.js server holds the JWT in an httpOnly
cookie and calls the API server-side, through Server Components for reads and Server Actions
for writes. There is no client-side `fetch` in the app. An XSS bug cannot read the token,
there is no CORS to configure, and no token ever reaches `localStorage`.

**Forms validate client-side, then submit through the same Server Action.** Every form uses
React Hook Form with a Yup schema from `src/schemas/`, so mistakes are caught before a request
ever goes out. A valid submission still resolves to the same `"use server"` action as before —
validation happens in addition to the server-side checks, not instead of them, so the API
remains the source of truth (an `OVERPAYMENT` rejection, for instance, can still only come from
the server, and the UI turns it into a one-click "Use $X" fix).

---

## API overview

Base URL `/api`. All order endpoints require `Authorization: Bearer <access token>`.

### Auth

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/auth/register/` | Create an account; returns an access + refresh pair |
| `POST` | `/api/auth/login/` | Exchange email + password for tokens |
| `POST` | `/api/auth/refresh/` | Rotate the access token |
| `POST` | `/api/auth/logout/` | Blacklist a refresh token |
| `GET` | `/api/auth/me/` | The current user |

### Orders

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/orders/` | List. Filters: `status` (repeatable), `customer`, `due_before`, `due_after`, `created_before`, `created_after`, `ordering`, `page` |
| `POST` | `/api/orders/` | Create with nested line items |
| `GET` | `/api/orders/{id}/` | Detail: line items, payments, refunds, totals, lock state |
| `PATCH` | `/api/orders/{id}/` | Update (subject to the locking rule below) |
| `DELETE` | `/api/orders/{id}/` | Delete; `409` once settlements exist |
| `GET`/`POST` | `/api/orders/{id}/payments/` | List / record a payment |
| `GET`/`POST` | `/api/orders/{id}/refunds/` | List / record a refund |
| `GET` | `/api/orders/{id}/audit-log/` | Event and status history |
| `GET` | `/api/orders/export/` | CSV; `?from=&to=` over `created_at`, plus every list filter |
| `GET` | `/api/summary/` | Dashboard tiles: counts and amounts per status |

Create an order:

```http
POST /api/orders/
{
  "customer": "Acme Corporation",
  "due_date": "2026-08-18",
  "line_items": [
    {"description": "Consulting day", "quantity": 2, "unit_price": "500.00"}
  ]
}
```

Record a payment:

```http
POST /api/orders/7/payments/
{"amount": "400.00", "paid_on": "2026-08-11", "note": "Deposit"}
```

### Error responses

Every failure — validation, business rule, auth, 404 — has the same shape:

```json
{
  "error": {
    "code": "OVERPAYMENT",
    "message": "A payment of $700.00 would exceed the amount due on this order. The most you can record is $600.00.",
    "details": {
      "field": "amount",
      "order_total": "1000.00",
      "amount_paid": "400.00",
      "max_allowed": "600.00",
      "attempted": "700.00"
    }
  }
}
```

`message` is written to be shown to a person unchanged, and where a rule was broken it names
the way out. `details` carries the machine-readable part: the payment form reads
`max_allowed` and offers a "Use $600.00" button, so the error is a fix rather than a wall.

| Code | HTTP | Meaning |
|---|---|---|
| `VALIDATION_ERROR` | 400 | Bad input; `details.fields` maps field → messages |
| `OVERPAYMENT` | 400 | Payment exceeds the outstanding balance |
| `OVER_REFUND` | 400 | Refund exceeds the net amount received |
| `ORDER_LOCKED` | 409 | Line items frozen; `details.editable_fields` lists what is not |
| `CONFLICT` | 409 | Delete blocked because settlements exist |
| `AUTH_REQUIRED` | 401 | Missing or expired credentials |
| `NOT_FOUND` | 404 | No such record, **or** it belongs to another account |

---

## Status derivation rules

**Status is derived, never stored.** `overdue` depends on today's date, so a persisted status
column would go stale the moment a due date passed without anyone writing to the row — you
would need a nightly job just to keep it honest. Instead the rule set lives in two mirrored
implementations in `orders/selectors.py`:

- `derive_status(...)` — Python, used when serialising a single object and when writing audit
  entries inside a transaction.
- `orders_with_status(...)` — the equivalent SQL `CASE` expression, so `?status=overdue`
  filtering, ordering and pagination all happen in the database rather than in memory over an
  unbounded result set.

Having one rule in two languages is a bug waiting to happen, so
`test_python_and_sql_status_agree_for_every_combination` builds an order for every
combination of (amount paid × due date) and asserts the two agree on all of them.

**The clause order is the specification.** Evaluated top to bottom, first match wins:

| # | Status | Condition |
|---|---|---|
| 1 | `paid` | `amount_paid >= total` |
| 2 | `overdue` | `due_date < today` (and not fully paid) |
| 3 | `partially_paid` | `amount_paid > 0` (and not fully paid, not past due) |
| 4 | `pending` | otherwise — no payments recorded |

`amount_paid` is the **net** figure: total payments minus total refunds.

---

## Edge cases

**An order that was overdue but is now fully paid reports `paid`, not `overdue`.**
This is the case the brief asks about. `paid` is checked first precisely so that settling a
late invoice closes it rather than leaving it flagged forever. The history of the lateness is
not lost — the audit log records the `overdue → paid` transition with its timestamp, which is
where "was this paid late?" should be answered from, not from the current status.

**An unpaid order past its due date is `overdue`, not `pending`.**
`overdue` outranks both `pending` and `partially_paid`. Otherwise the dashboard would report
an unpaid, three-months-late order as merely "pending".

**An order due *today* is not overdue.** The comparison is `due_date < today`, so payment is
expected up to the end of the due date. Dates are compared in the server's configured
timezone (`DJANGO_TIME_ZONE`, default UTC).

**A refund can reopen a settled order.** Refunding $250 against a paid $1,000 order returns
it to `partially_paid` with $250 due; if it is also past its due date it becomes `overdue`
again. Refunding everything returns it to `pending`.

**Paying the exact remainder settles the order.** `>= total`, not `> total`. Four payments of
$250 on a $1,000 order land on `paid` with `amount_due` of exactly `0.00`.

**An order cannot total zero.** Creation is rejected if the computed total is not greater
than zero, so a $0 order can never sit in an ambiguous state.

**Money is never a float.**
Every amount is a `Decimal` quantised to two places, and the API serialises amounts as
*strings* so they survive JSON intact. The `amount_due` annotation (`F("total") -
F("amount_paid")`) relies on Postgres's exact numeric arithmetic, so it is exact to the cent
without any extra rounding in SQL. `test_amount_due_annotation_is_exact_to_the_cent` guards it.
The frontend does its live subtotal preview in integer cents for the same reason.

---

## Decisions and rationale

### Orders become partly read-only after the first payment

**Rule:** once an order has any payment or refund, its **line items — and therefore its
total — are frozen**. `customer` and `due_date` stay editable for the order's whole life.
Editing a locked field returns `409 ORDER_LOCKED` naming the fields that are still editable,
and the UI stops offering the controls.

**Why.** Lowering the total below what has already been paid would retroactively create an
over-paid order and break the invariant everything else rests on. Beyond the arithmetic,
rewriting the amounts after money has changed hands makes the payment history a record of
something that no longer exists — the whole point of keeping payments is that they attest to
an agreed figure. Customer name and due date carry no arithmetic risk: renaming a customer or
renegotiating a date is ordinary business, and locking those would be an annoyance with no
protective value.

The service also refuses, independently, to set a total below `amount_paid`. That check is
unreachable while the lock holds, and is kept deliberately as a second line of defence if the
locking policy is ever relaxed.

### Deleting an order with settlements is blocked

`DELETE` returns `409` once a payment or refund exists. Payment history is a financial record
and a cascading delete would destroy evidence of money received. The error suggests refunding
instead. Deletion stays available for orders raised in error, before any money moves.

### Refunds are a separate entity, not negative payments

The brief allows either. A separate `Refund` model keeps `Payment.amount >= 0.01` literally
true rather than a rule with an exception, keeps "sum of payments" meaning what it says, and
gives refunds their own `reason` and `refunded_on` fields plus an optional link to the payment
they reverse. Net paid is `Σ payments − Σ refunds`, maintained on `Order.amount_paid`.

The cost is one more table and a second code path to keep in step with the payment path. That
felt like the better trade against a `Payment` table where the sign of a column silently
changes what a row means.

### Totals are denormalised onto the order

`Order.total` and `Order.amount_paid` are stored, recomputed inside the same transaction as
the rows they summarise. They could be aggregated on read instead. Storing them buys two
things: the database can enforce `amount_paid <= total` as a `CheckConstraint` — an invariant
no code path, shell session or migration can break — and the dashboard can sort, filter and
paginate on money without an aggregate subquery per row. The cost is that they must be
maintained transactionally, which is exactly what the services layer is for.

### 404 rather than 403 for another user's data

Requesting an order belonging to someone else returns `404`, not `403`. A `403` would confirm
that the id exists. Ownership is part of the lookup itself (`get(pk=..., owner=user)`), not a
permission check layered on afterwards, so there is no code path where the filter can be
forgotten.

### Tokens in httpOnly cookies, held server-side

Access and refresh tokens live in httpOnly cookies and are attached to API calls by the
Next.js server. No token is ever readable by browser JavaScript. Access tokens last 30
minutes, refresh tokens 7 days with rotation and blacklisting on use. Renewal happens in
`src/proxy.ts` — Server Components are not allowed to write cookies during a render, so doing
it in the request-level proxy is what keeps page loads working after a token lapses.

---

## Concurrency

**The scenario.** Two payments of $600 are submitted against a $1,000 order at the same
instant. Each fits on its own. Naively, both requests read `amount_paid = 0`, both conclude
there is room, and both commit — leaving the order paid $1,200 against a $1,000 total.

**What this project does.** `record_payment` and `record_refund` open a transaction and take
a row lock before reading the balance:

```python
with transaction.atomic():
    order = Order.objects.select_for_update().get(pk=order_id, owner=user)
    max_allowed = order.total - order.amount_paid
    if amount > max_allowed:
        raise OverpaymentError(...)
    ...
```

The second transaction blocks on `SELECT ... FOR UPDATE` until the first commits, then reads
the *updated* balance and is correctly rejected. `test_simultaneous_payments_cannot_overpay`
fires two real threads at one order through a barrier and asserts exactly one succeeds.

**Three layers, deliberately.** The row lock is correctness. The
`CheckConstraint(amount_paid <= total)` on the table is the backstop — even a write that
bypasses the services layer entirely cannot break the invariant, and
`test_database_constraint_backstops_the_service_check` proves it by trying. The submit button
disabling itself while a request is in flight is a convenience that stops accidental
double-clicks; it is not relied on for anything, because nothing in a browser can be.

Because each service call is a single `transaction.atomic()` block, a rejected payment leaves
nothing behind: no `Payment` row, no changed balance, no audit entry.

**Limits.** `SELECT ... FOR UPDATE` serialises writers on one order across all application
instances sharing the database, which is the right granularity here — contention is per
order, and orders are independent. It does not survive a move to multiple databases or an
eventually-consistent store. At much higher volume I would put payments through a per-order
queue or an append-only ledger with the balance as a materialised projection, so writers
never block each other.

---

## Assumptions and tradeoffs

- **Single currency (USD), no tax or discounts.** The brief states order total equals
  subtotal. Amounts are `DECIMAL(12,2)`, which caps an order at just under $10^10.
- **No partial-payment allocation to specific line items.** Payments settle the order as a
  whole. Line-item-level allocation is a meaningfully different data model and the brief does
  not ask for it.
- **`quantity` is a positive integer.** Fractional quantities (hours, kilograms) would need a
  decimal column; nothing in the brief suggests them.
- **`unit_price` may be zero** (a free line on a paid order), but the order total may not be.
- **Dates are dates, not timestamps.** `due_date` and `paid_on` are calendar dates, compared
  in the server timezone. A payment can be back-dated; nothing forbids a `paid_on` in the
  past, which matches how payments are actually reconciled.
- **The audit log is best-effort, not a ledger.** It is written in the same transaction as the
  change, so it cannot drift, but it is a history view rather than the source of truth for
  balances. `Order.amount_paid` is.
- **Pagination is 20 per page** (`?page_size=` up to 100). The dashboard shows the first page
  with a count; I did not build pagination controls, which is a gap in the UI rather than the
  API.
- **CSV export is filtered by `created_at`**, not `due_date`. Both are defensible; `created_at`
  matches "orders raised in this period", which is the more common reporting question. Every
  list filter also applies, so a due-date range export is available via `?due_after=&due_before=`.
- **Postgres only, no zero-setup fallback.** Row-level locking is load-bearing for the
  overpayment/overrefund invariant, so the app requires `DATABASE_URL` and fails fast without it.

---

## What I would do before production

1. **Idempotency keys on payment POSTs.** The row lock stops two *different* payments from
   over-paying, but a retried request after a timeout would record the same payment twice. An
   `Idempotency-Key` header with a uniqueness constraint is the standard fix and the most
   important gap here.
2. **Rate limiting on the auth endpoints.** Login is currently unthrottled and open to
   credential stuffing. DRF throttling plus lockout after repeated failures.
3. **An OpenAPI schema** via `drf-spectacular`, with the frontend types generated from it
   rather than hand-maintained in `src/lib/types.ts`.
4. **Structured logging and error reporting.** JSON logs with a request id, and Sentry on both
   apps. Right now a 500 is only visible in the console.
5. **Soft deletes.** Even unpaid orders currently disappear on `DELETE`. A `deleted_at` column
   preserves the record and makes the operation reversible.
6. **Money as a value object, and multi-currency.** A `currency` column alongside every
   amount, and arithmetic that refuses to mix currencies.
7. **Background jobs for exports.** A streaming CSV holds a request open; past a certain size
   it should be generated by a worker and delivered as a link.
8. **Pagination and search in the dashboard UI**, and optimistic updates on the payment form.
9. **Browser-level end-to-end tests.** The API is well covered and the frontend's money
   handling is unit tested, but the click-through path has no automated coverage — a Playwright
   run of the sample scenario is the obvious first one.
10. **Email verification and password reset**, neither of which the brief required.

---

## Deployment

Not yet deployed. The application is deployment-ready in the following sense: the backend is
fully environment-driven (`DATABASE_URL`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`,
`CORS_ALLOWED_ORIGINS`), ships `gunicorn` and `whitenoise`, and enables SSL redirect, HSTS and
secure cookies automatically when `DJANGO_DEBUG=false`; the frontend needs only
`API_BASE_URL`. The intended target is the Django API and a managed Postgres on one platform,
with the Next.js app deployed separately and pointed at the API's public URL.

The live URL will be added here and to the submission email once deployed.

---

## Verification status

Honest summary of what has and has not been checked:

| Checked | How |
|---|---|
| Backend logic and API | `pytest`: 91 passed, run against Postgres |
| The brief's sample scenario | Asserted as a test **and** run against the live API with `curl` |
| Over-payment error payloads | Verified live, both the "already paid in full" and "most you can record" variants |
| Frontend types, lint, production build | `tsc --noEmit`, `biome check`, `next build` — all clean |
| Frontend money handling | 10 unit tests (`vitest`) |
| Auth routing | Verified live: unauthenticated `/` and `/orders/1` return 307 to `/login`, `/login` returns 200 |
| Authenticated UI rendering | Verified live in a browser against the running API: login, dashboard, order detail, recording a payment (including the over-payment rejection and its "Use $X" fix-it button), and creating a new order were all exercised end to end, at both desktop and mobile widths |
