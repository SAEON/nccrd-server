from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from nccrd.api.routers import submission, region, rbac, vocabulary
from nccrd.api.routers.submission import PROGRESS_REPORT_UPLOAD_DIR
from nccrd.version import VERSION

app = FastAPI(
    title="NCCRD API",
    version=VERSION,
    docs_url='/swagger',
    redoc_url='/docs',
)

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
    # allow_origins=config.ODP.API.ALLOW_ORIGINS,
    allow_origins=[
        "http://nccrd.localhost:2021",
        "http://localhost:5024",
        "http://127.0.0.1:5024",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175"
    ],  # Add frontend domain here
    allow_methods=["*"],
    allow_headers=["*"],
)
