from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from nccrd.api.routers import auth, submission, region, rbac, vocabulary
from nccrd.api.routers.submission import PROGRESS_REPORT_UPLOAD_DIR
from nccrd.config import nccrd_config
from nccrd.version import VERSION

app = FastAPI(
    title="NCCRD API",
    version=VERSION,
    docs_url='/swagger',
    redoc_url='/docs',
)

@app.get('/health', tags=['Health'])
def health():
    """Liveness check for the container's HEALTHCHECK — no auth, no DB
    round-trip, just confirms the ASGI app itself is up and serving."""
    return {"status": "ok", "version": VERSION}


app.include_router(auth.router, prefix='/auth', tags=['Auth'])
app.include_router(submission.router, prefix='/submission', tags=['Submission'])
app.include_router(region.router, prefix='/region', tags=['Region'])
app.include_router(rbac.router, prefix='/rbac', tags=['RBAC'])
app.include_router(vocabulary.router, prefix='/vocabulary', tags=['Vocabulary'])

# Serves progress-report (MRV) uploads back out — file_url values point here.
app.mount(
    "/uploads/progress_reports",
    StaticFiles(directory=PROGRESS_REPORT_UPLOAD_DIR),
    name="progress_report_uploads",
)

# app.include_router(survey.router, prefix='/survey', tags=['Survey'])
# app.include_router(survey_download.router, prefix='/survey/download', tags=['Survey', 'Download'])
# app.include_router(vos_survey.router, prefix='/vos_survey', tags=['Survey'])
# app.include_router(download_audit.router, prefix='/downloads', tags=['Downloads', 'Audit'])

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in nccrd_config.NCCRD.CORS_ORIGINS.split(',') if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)
