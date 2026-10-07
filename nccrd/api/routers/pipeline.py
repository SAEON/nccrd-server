"""
API router: a read-only view of the data pipeline (nccrd-build/pipeline) for
curators. It shows what each source last loaded and what the app holds from it,
the projects changed in the app that their source also changed (conflicts), and
the data-quality issues the pipeline found, with the projects they affect.

The pipeline keeps its own schemas (``bronze``, ``silver``, ``pipeline``) in
this database. They aren't part of the app's models or migrations, so this
reads them with plain SQL and answers ``available: false`` on a database the
pipeline has never run against. Loading data stays with the pipeline's command
line (PIPELINE.md).
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from nccrd.api.lib.auth import Authorized
from nccrd.api.lib.permissions import RequirePermission
from nccrd.api.routers.submission import REVIEW_PERMISSION
from nccrd.db import get_db

router = APIRouter()

#: Source rows that are projects in the app now (linked by the pipeline, not deleted).
_IN_APP = """
    JOIN pipeline.sync_state st ON st.data_source = d.data_source AND st.source_key = d.source_key
    JOIN nccrd.submission g ON g.id = st.gold_id AND NOT g.deleted
"""


def _exists(db: Session, table: str) -> bool:
    return bool(db.execute(text("SELECT to_regclass(:t) IS NOT NULL"), {"t": table}).scalar())


def _rows(db: Session, sql: str, **params) -> List[Dict[str, Any]]:
    return [dict(r._mapping) for r in db.execute(text(sql), params)]


@router.get(
    "/status",
    summary="What the data pipeline loaded, conflicts with app edits, and data-quality issues (curators).",
)
def pipeline_status(
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission(REVIEW_PERMISSION)),
) -> Dict[str, Any]:
    if not all(_exists(db, t) for t in ("pipeline.load_batch", "pipeline.sync_state", "silver.submission")):
        return {"available": False}

    loads = _rows(db, """
        SELECT DISTINCT ON (source) source, file_name, loaded_at
        FROM pipeline.load_batch ORDER BY source, id DESC""")
    sources = _rows(db, """
        SELECT d.data_source,
               (SELECT count(*) FROM silver.submission s WHERE s.data_source = d.data_source) AS in_source,
               (SELECT count(*) FROM pipeline.curation c
                 WHERE c.data_source = d.data_source AND c.action = 'exclude') AS excluded,
               (SELECT count(*) FROM nccrd.submission g
                 WHERE g.data_source = d.data_source AND NOT g.deleted) AS in_app,
               (SELECT count(*) FROM nccrd.submission g
                 WHERE g.data_source = d.data_source AND NOT g.deleted AND g.issubmitted
                   AND g.submission_status = 'Accepted') AS public
        FROM (SELECT DISTINCT data_source FROM silver.submission) d ORDER BY 1""")
    runs = _rows(db, """
        SELECT kind, ran_at, summary FROM pipeline.run WHERE applied ORDER BY id DESC LIMIT 10""")
    conflicts = _rows(db, """
        SELECT c.gold_id::text AS id, c.data_source, c.reason, c.fields, g.title
        FROM silver.sync_conflict c JOIN nccrd.submission g ON g.id = c.gold_id
        WHERE NOT EXISTS (SELECT 1 FROM pipeline.curation x WHERE x.data_source = c.data_source
                          AND x.source_key = c.source_key AND x.action = 'exclude')
        ORDER BY c.data_source, g.title""") if _exists(db, "silver.sync_conflict") else []
    issues = _rows(db, f"""
        SELECT d.data_source, d.field, d.issue, count(DISTINCT g.id) AS projects
        FROM silver.dq_issue d {_IN_APP}
        GROUP BY 1, 2, 3 ORDER BY 1, 4 DESC""") if _exists(db, "silver.dq_issue") else []
    return {"available": True, "loads": loads, "sources": sources, "runs": runs,
            "conflicts": conflicts, "issues": issues}


@router.get(
    "/issues",
    summary="Projects in the app affected by one data-quality issue (curators' worklist).",
)
def pipeline_issue_projects(
        data_source: str,
        field: str,
        issue: str,
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        db: Session = Depends(get_db),
        auth: Authorized = Depends(RequirePermission(REVIEW_PERMISSION)),
) -> Dict[str, Any]:
    if not all(_exists(db, t) for t in ("silver.dq_issue", "pipeline.sync_state")):
        return {"total": 0, "projects": []}
    where = "WHERE d.data_source = :ds AND d.field = :field AND d.issue = :issue"
    params = {"ds": data_source, "field": field, "issue": issue}
    total: Optional[int] = db.execute(text(f"SELECT count(DISTINCT g.id) FROM silver.dq_issue d {_IN_APP} {where}"),
                                      params).scalar()
    projects = _rows(db, f"""
        SELECT DISTINCT ON (g.title, g.id) g.id::text AS id, g.title, g.implementation_organization,
               g.issubmitted AND g.submission_status = 'Accepted' AS public, d.value
        FROM silver.dq_issue d {_IN_APP} {where}
        ORDER BY g.title, g.id LIMIT :limit OFFSET :offset""", **params, limit=limit, offset=offset)
    return {"total": total or 0, "projects": projects}
