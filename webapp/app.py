"""FastAPI application for the public subtitle web shell."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse

from webapp.service import (
    ALLOWED_VIDEO_EXTENSIONS,
    InvalidJobOptionsError,
    QueueFullError,
    QuotaExceededError,
    WebRuntime,
    WebSettings,
    make_job_id,
    save_upload_file,
    validate_job_options,
)

ROOT_DIR = Path(__file__).resolve().parent.parent
INDEX_PATH = Path(__file__).resolve().with_name("index.html")


@asynccontextmanager
async def lifespan(app: FastAPI):
    runtime = WebRuntime(WebSettings.from_env(ROOT_DIR))
    runtime.start()
    app.state.runtime = runtime
    try:
        yield
    finally:
        runtime.stop()


app = FastAPI(title="Subtitle Pipeline Web", lifespan=lifespan)


def _runtime(request: Request) -> WebRuntime:
    return request.app.state.runtime


def _parse_checkbox(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "on", "yes"}


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_PATH.read_text(encoding="utf-8")


@app.get("/healthz")
async def healthz(request: Request) -> dict[str, str]:
    runtime = _runtime(request)
    return {"status": "ok", "data_dir": str(runtime.settings.data_dir)}


@app.get("/api/public/status")
async def public_status(request: Request) -> dict[str, object]:
    return _runtime(request).store.get_public_status()


@app.post("/api/jobs", status_code=201)
async def create_job(
    request: Request,
    video: UploadFile = File(...),
    model: str = Form("medium"),
    zh_script: str = Form("simplified"),
    burn_subtitles: str | None = Form(None),
    ai_review: str | None = Form(None),
) -> JSONResponse:
    runtime = _runtime(request)
    settings = runtime.settings

    filename = video.filename or "upload.mp4"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail="unsupported video format")

    options = validate_job_options(
        {
            "model": model,
            "zh_script": zh_script,
            "burn_subtitles": _parse_checkbox(burn_subtitles),
            "ai_review": _parse_checkbox(ai_review),
        }
    )

    job_id = make_job_id()
    job_dir = settings.jobs_dir / job_id
    output_dir = job_dir / "output"
    log_path = job_dir / "job.log"
    upload_path = settings.uploads_dir / f"{job_id}{suffix}"

    try:
        await video.seek(0)
        bytes_written = save_upload_file(video.file, upload_path, settings.max_upload_mb * 1024 * 1024)
        runtime.store.create_job(
            job_id=job_id,
            original_filename=filename,
            upload_path=upload_path,
            output_dir=output_dir,
            log_path=log_path,
            options=options,
        )
    except QuotaExceededError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except QueueFullError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except InvalidJobOptionsError as exc:
        upload_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return JSONResponse(
        {
            "job_id": job_id,
            "status": "queued",
            "filename": filename,
            "size_bytes": bytes_written,
        },
        status_code=201,
    )


@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str, request: Request) -> dict[str, object]:
    job = _runtime(request).store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    for key in ("upload_path", "output_dir", "log_path"):
        job.pop(key, None)
    return job


@app.get("/api/jobs/{job_id}/log", response_class=PlainTextResponse)
async def get_job_log(job_id: str, request: Request) -> str:
    job = _runtime(request).store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return str(job["log_tail"])


@app.get("/api/jobs/{job_id}/files/{filename}")
async def download_job_file(job_id: str, filename: str, request: Request) -> FileResponse:
    job = _runtime(request).store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")

    output_dir = Path(str(job["output_dir"])).resolve()
    target = (output_dir / filename).resolve()
    if target.parent != output_dir or not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file not found")

    return FileResponse(target, filename=filename)
