# Web Shell

This project now includes a public web shell on top of the existing CLI pipeline.

## What It Does

- Serves a browser-based upload page
- Accepts anonymous subtitle jobs
- Applies a global daily anonymous quota
- Runs jobs serially by invoking `auto_subtitle.py`
- Stores logs and output files on disk for later download

## Local Start

```bash
python -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.web.example .env.web.local
./run_web.sh
```

Windows:

```bat
py -3 -m venv .venv
.venv\Scripts\pip.exe install -r requirements.txt
copy .env.web.example .env.web.local
run_web.bat
```

Default URL: `http://127.0.0.1:8000`

## Public Deployment

Use Docker Compose:

```bash
cp .env.web.example .env.web.local
docker compose up -d --build
```

The service stores runtime data in `web_data/`.

## Environment Variables

- `WEB_DAILY_QUOTA`: global anonymous jobs per day
- `WEB_MAX_UPLOAD_MB`: max upload size in megabytes
- `WEB_MAX_QUEUE_SIZE`: max queued jobs
- `WEB_JOB_TIMEOUT_SECONDS`: timeout for each job
- `WEB_RESULT_TTL_HOURS`: how long finished files are kept
- `WEB_TIMEZONE`: quota reset timezone

## API

- `GET /api/public/status`
- `POST /api/jobs`
- `GET /api/jobs/{job_id}`
- `GET /api/jobs/{job_id}/log`
- `GET /api/jobs/{job_id}/files/{filename}`
