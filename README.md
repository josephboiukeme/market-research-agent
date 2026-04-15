# Market Research Agent

> ⚠️ **DISCLAIMER**: This project is an automated AI research assistant provided for
> **informational and educational purposes only**. Nothing in this repository or any report it
> generates constitutes financial advice, investment advice, a solicitation, or a recommendation
> to buy or sell any security or financial instrument.  Always consult a licensed financial
> professional before making investment decisions.  Past performance of any signal is not
> indicative of future results.

---

An agentic end-of-day (EOD) market research assistant powered by **Groq / Llama**, with:

- 📊 **Market data** via yfinance (unofficial Yahoo Finance wrapper — see note below)
- 🧠 **Trend scoring** — deterministic composite ranking (daily %, volume anomaly, volatility proxy)
- 🤖 **LLM narrative** — Groq API with a Llama open-source model for market summary, recommendations, and behavior coaching
- 📧 **Email delivery** via SMTP (e.g. Gmail App Password)
- 🗄️ **Postgres memory** — SQLAlchemy models tracking runs, recommendations, user feedback, and behavior tags
- 🖥️ **CLI** powered by Typer (`market-agent`)
- ⏰ **Local cron** scheduling (example included)

---

## Quick Start (Ubuntu VM)

### 1 · Prerequisites

```bash
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib libpq-dev
```

### 2 · Clone & set up the virtual environment

```bash
git clone https://github.com/josephboiukeme/market-research-agent.git
cd market-research-agent

chmod +x scripts/setup_venv.sh
./scripts/setup_venv.sh

source venv/bin/activate
```

### 3 · Configure environment variables

```bash
cp .env.example .env
nano .env          # fill in your keys and credentials
```

Key variables to set:

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (get one free at [console.groq.com](https://console.groq.com)) |
| `GROQ_MODEL` | Llama model name (default: `llama3-70b-8192`) |
| `DATABASE_URL` | Database connection string (default: `sqlite:///./data/market_agent.db`) |
| `SMTP_HOST` / `SMTP_PORT` | SMTP server (default: `localhost:25` — local relay, no auth) |
| `SMTP_TLS` | Enable STARTTLS; set `true` for external providers like Gmail (default: `false`) |
| `SMTP_USER` / `SMTP_PASSWORD` | Credentials — leave blank for unauthenticated local relay |
| `EMAIL_FROM` / `EMAIL_TO` | Sender and recipient email addresses |
| `WATCHLIST` | Comma-separated tickers (default: `SPY,QQQ,IWM,VTI,XLK,XLF,XLE`) |
| `TIMEZONE` | Timezone for timestamps (default: `America/New_York`) |

### 4 · Set up the database

**SQLite (default — no additional setup needed):**

The app defaults to SQLite at `data/market_agent.db`.  The `data/` directory is created
automatically on first run.

```bash
market-agent db init   # creates data/market_agent.db with all tables
```

**Postgres (optional — for production/VM use):**

```bash
sudo -u postgres psql << 'SQL'
CREATE USER market_agent WITH PASSWORD 'changeme';
CREATE DATABASE market_agent OWNER market_agent;
SQL
```

Update `DATABASE_URL` in `.env` to:

```
DATABASE_URL=postgresql+psycopg://market_agent:changeme@localhost:5432/market_agent
```

Then run `market-agent db init` to create the tables.

### 5 · Run once (dry-run — no Groq API calls, no email)

```bash
market-agent run-eod --dry-run --no-email
```

This fetches real market data and renders a report with stubbed LLM text.

### 6 · Run for real

```bash
market-agent run-eod
```

Requires `GROQ_API_KEY`, `SMTP_USER`, `SMTP_PASSWORD`, and `EMAIL_TO` to be set.

### 7 · Record feedback

```bash
# Record what you did after reviewing the report
market-agent feedback --action "held SPY" --ticker SPY --rating 4 --notes "Good signal, stayed patient"
```

---

## Hosting on GitHub Actions (SQLite persistence)

You can run the agent on a weekday schedule entirely within GitHub Actions — no VM required.
Behavior memory (SQLite DB) is persisted between runs via **GitHub Actions artifacts**.

### How it works

1. At the start of each run, the workflow downloads the latest `market-agent-db` artifact
   (which contains `data/market_agent.db`) if one exists.
2. The EOD pipeline runs and writes/updates the SQLite database at `data/market_agent.db`.
3. After the pipeline, both the DB and the generated report (`out/eod_report.md`) are uploaded
   as new artifacts with a 30-day retention window.

### Schedule

The default cron schedule is **21:00 UTC on weekdays (Monday–Friday)**:

- During **EDT (Mar–Nov)**: 21:00 UTC ≈ 5:00 pm ET (≈30 min after US market close)
- During **EST (Nov–Mar)**: 21:00 UTC ≈ 4:00 pm ET (≈30 min after US market close)

> **DST caveat**: UTC doesn't observe daylight saving time, so the run will always be at 21:00 UTC.
> This means it arrives ~30 min after the 4:30 pm ET close in both EDT and EST — no change needed.

You can also trigger it manually via **Actions → EOD Market Research Agent → Run workflow**.

### Required GitHub Secrets

Go to **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret name | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (get one free at [console.groq.com](https://console.groq.com)) |
| `SMTP_HOST` | SMTP server hostname (e.g. `smtp.gmail.com`) |
| `SMTP_PORT` | SMTP port (e.g. `587`) |
| `SMTP_TLS` | `true` or `false` |
| `SMTP_USER` | SMTP username / email address |
| `SMTP_PASSWORD` | SMTP password or App Password |
| `EMAIL_FROM` | Sender address (e.g. `you@gmail.com`) |
| `EMAIL_TO` | Recipient address for the EOD report |

Optional **repository variables** (Settings → Secrets and variables → Actions → Variables):

| Variable | Default | Description |
|---|---|---|
| `GROQ_MODEL` | `llama3-70b-8192` | Groq / Llama model name |
| `WATCHLIST` | `SPY,QQQ,IWM,VTI,XLK,XLF,XLE` | Comma-separated tickers |

### Enabling the workflow

The workflow file lives at `.github/workflows/eod.yml`.  Once pushed to `main` with valid secrets,
it will run automatically on the schedule above.  You can review logs and download artifacts from
the **Actions** tab in the GitHub repository.

---



US Eastern 4:30 PM = **21:30 UTC** (EST) / **20:30 UTC** (EDT).

```bash
# Install crontab entry:
crontab -e
```

Add the following line (adjust path):

```
30 21 * * 1-5 /home/youruser/market-research-agent/scripts/run_eod.sh >> /home/youruser/market-research-agent/logs/eod.log 2>&1
```

See `scripts/cron.example` for more details and a commented template.

---

## CLI Reference

```
market-agent --help

Commands:
  run-eod   Run the end-of-day market research pipeline.
  db        Database management commands.
  feedback  Record what you did after reviewing the EOD report.
```

### `run-eod`

```
market-agent run-eod [OPTIONS]

  Options:
    --as-of DATE     Reference date YYYY-MM-DD (default: today)
    --dry-run        Use stubbed LLM output; skip Groq API calls
    --no-email       Generate report but do not send email
    --top-n INT      Number of focus tickers (default: 3)
    --output PATH    Write the markdown report to this file path
```

### `db init`

```
market-agent db init   # Creates all database tables (idempotent; works with SQLite and Postgres)
```

### `feedback`

```
market-agent feedback [OPTIONS]

  Options:
    --run-id TEXT    Run ID (default: most recent run)
    --ticker TEXT    Ticker the action relates to
    --action TEXT    What you actually did (e.g. "bought SPY")
    --rating INT     1-5 rating for recommendation quality
    --notes TEXT     Additional notes
```

---

## Project Structure

```
market-research-agent/
├── src/market_agent/
│   ├── config.py             # Pydantic Settings (loads .env)
│   ├── groq_client.py        # Groq API wrapper (retries, dry-run, structured output)
│   ├── pipeline.py           # EOD orchestration
│   ├── cli.py                # Typer CLI entry-point
│   ├── data_sources/
│   │   └── yfinance_source.py   # yfinance market data fetcher
│   ├── analysis/
│   │   └── trend_scoring.py  # Deterministic composite score
│   ├── reporting/
│   │   ├── report_generator.py  # Assembles Jinja2 template + LLM sections
│   │   └── eod_template.md.j2   # Jinja2 markdown template
│   ├── notify/
│   │   └── emailer.py        # SMTP sender
│   └── memory/
│       ├── models.py          # SQLAlchemy ORM models
│       ├── db.py              # Engine + session factory + init_db()
│       └── repository.py     # CRUD helpers
├── scripts/
│   ├── setup_venv.sh          # Create venv and install deps
│   ├── run_eod.sh             # Wrapper script (for cron)
│   └── cron.example           # Example crontab entry
├── db/
│   └── init.sql               # Optional manual SQL schema
├── logs/
│   └── .gitkeep
├── tests/
│   └── test_smoke.py          # Smoke tests (no network/DB required)
├── .env.example
├── .gitignore
└── pyproject.toml
```

---

## Running Tests

```bash
source venv/bin/activate
pytest -v
```

Tests run without any external connections — Groq, SMTP, and Postgres are all mocked or bypassed.

---

## Email Delivery

The notifier supports two modes — no code change required, just `.env` settings.

### Option A — Unauthenticated local relay (recommended for VMs)

Install Postfix once:

```bash
sudo apt install -y postfix
# Choose "Internet Site" and enter your hostname when prompted
```

`.env` settings (these are the defaults — nothing extra to set):

```ini
SMTP_HOST=localhost
SMTP_PORT=25
SMTP_TLS=false
SMTP_USER=
SMTP_PASSWORD=
EMAIL_FROM=market-agent@yourhostname
EMAIL_TO=you@example.com
```

No authentication, no TLS, no app password needed.  Postfix relays outbound mail on your behalf.

### Option B — Authenticated external relay (e.g. Gmail)

```ini
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_TLS=true
SMTP_USER=you@gmail.com
SMTP_PASSWORD=your_app_password
EMAIL_FROM=you@gmail.com
EMAIL_TO=you@gmail.com
```

See **Gmail App Password Setup** below for how to generate `SMTP_PASSWORD`.

---

## Notes on Data Sources

**yfinance** is an unofficial, community-maintained wrapper around Yahoo Finance.  It is free and
requires no API key, but:

- Usage is subject to Yahoo's terms of service.
- Rate limits may apply.
- Data quality may vary; there is no SLA.

For production deployments, consider a paid, licensed data provider such as
[Polygon.io](https://polygon.io), [Alpaca](https://alpaca.markets), or
[Tiingo](https://www.tiingo.com).  The `data_sources/` module is designed to be swappable.

---

## Gmail App Password Setup

1. Enable 2-Step Verification on your Google account.
2. Go to **Google Account → Security → App Passwords**.
3. Create a new App Password for "Mail / Other".
4. Use the 16-character password as `SMTP_PASSWORD` in `.env`.