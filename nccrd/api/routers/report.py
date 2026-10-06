"""
Public data reports: summary figures, data-quality metrics and exports.

Every endpoint takes the same filters as the project search
(``SubmissionFilters``) and sees the same tenant-scoped, non-deleted
submissions, so a report always describes exactly what the search shows.
Vocabulary-backed values are flattened to plain terms with ``_vocab_terms``,
whatever legacy shape they are stored in.
"""
import csv
import io
import re
from collections import Counter
from datetime import date
from statistics import median
from typing import Any, Dict, Iterable, List, Literal, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from openpyxl import Workbook
from sqlalchemy.orm import Session

from nccrd.api.lib.tenant import get_current_tenant
from nccrd.api.routers.submission import SubmissionFilters, _vocab_terms, filtered_submissions, merge_case_variants
from nccrd.db import get_db
from nccrd.db.models import Adaptation, Mitigation, Submission
from nccrd.db.models.rbac import DownloadLog, Tenant

router = APIRouter()

NOT_SPECIFIED = "Not specified"
TOP_N = 12


# ──────────────────────────────────────────────────────────────────────────────
# Loading
# ──────────────────────────────────────────────────────────────────────────────


def _load(db: Session, tenant: Tenant, filters: SubmissionFilters):
    """Filtered submissions plus their mitigation/adaptation rows by submission id."""
    query = filtered_submissions(db, tenant, filters)
    submissions = query.all()
    ids = query.with_entities(Submission.id)
    mitigation = {m.submission_id: m for m in db.query(Mitigation).filter(Mitigation.submission_id.in_(ids))}
    adaptation = {a.submission_id: a for a in db.query(Adaptation).filter(Adaptation.submission_id.in_(ids))}
    return submissions, mitigation, adaptation


def _geo(submission: Submission) -> Dict[str, Any]:
    return submission.geo_location if isinstance(submission.geo_location, dict) else {}


#: Rough bounding box of South Africa (lat, lon), to drop placeholder or
#: mistyped points. Generous enough for every real project location.
_SA_LAT, _SA_LON = (-35.5, -21.5), (15.5, 33.5)
_WKT_POINT = re.compile(r"POINT\s*\(\s*(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s*\)")


def _points(submission: Submission) -> List[tuple]:
    """
    The project's real locations as (lat, lon) pairs. ``coordinates`` holds
    either a [lon, lat] pair ([0, 0] = no location) or, for legacy rows, WKT
    text such as "GEOMETRYCOLLECTION (POINT (28.1 -26.2), POINT (...))" that
    can list several places.
    """
    c = _geo(submission).get("coordinates")
    if isinstance(c, list) and len(c) == 2 and all(isinstance(v, (int, float)) for v in c):
        pairs = [(c[1], c[0])]
    elif isinstance(c, str):
        pairs = [(float(lat), float(lon)) for lon, lat in _WKT_POINT.findall(c)]
    else:
        pairs = []
    return [
        (lat, lon) for lat, lon in pairs
        if _SA_LAT[0] <= lat <= _SA_LAT[1] and _SA_LON[0] <= lon <= _SA_LON[1]
    ]


def _coordinates(submission: Submission) -> Optional[tuple]:
    """The project's first real location, (lat, lon), or None."""
    points = _points(submission)
    return points[0] if points else None


def _blank(value: Any) -> bool:
    return not _vocab_terms(value) if not isinstance(value, (int, float)) else False


# ──────────────────────────────────────────────────────────────────────────────
# Summary
# ──────────────────────────────────────────────────────────────────────────────


def _counts(values: Iterable[Iterable[str]], top: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Count projects per term. Each item is one project's list of terms, so a
    project spanning two provinces counts once in each; a project with none
    counts under "Not specified" (always listed last).
    """
    per_project, unspecified = [], 0
    for terms in values:
        # One count per project, even if it lists "Energy" and "ENERGY".
        terms = {t.casefold(): t for t in terms}.values()
        if terms:
            per_project.extend((t, 1) for t in terms)
        else:
            unspecified += 1
    counter = merge_case_variants(per_project)
    rows = [{"label": k, "count": v} for k, v in counter.most_common(top)]
    if unspecified:
        rows.append({"label": NOT_SPECIFIED, "count": unspecified})
    return rows


#: Project types in their fixed display order (series of the by-type charts).
TYPES = ["Mitigation", "Adaptation", "Cross Cutting"]

#: Official "budgetRanges" vocabulary, smallest first.
BUDGET_RANGES = [
    "< R10k", "R10k - R50K", "R50k - R100k", "R100k - R500k", "R500k - R1m",
    "R1m - R5m", "R5m - R10m", "R10m - R50m", "R50m - R100m", "> R100m",
]

_FINISHED = {"completed", "cancelled"}


def _years_under_way(s: Submission, this_year: int) -> range:
    """
    Calendar years a project was under way: start year to end year. With no
    end date, an unfinished project runs to this year and a finished one counts
    in its start year only. Future years and end-before-start are clamped.
    """
    if not s.start_date:
        return range(0)
    start = s.start_date.year
    if s.end_date:
        end = s.end_date.year
    elif (s.implementation_status or "").strip().lower() in _FINISHED:
        end = start
    else:
        end = this_year
    return range(start, max(start, min(end, this_year)) + 1)


def _by_type(rows: Iterable[tuple], order: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    A category x project-type count table from (category, type) pairs, for the
    stacked charts. Categories keep ``order`` when given (missing ones are
    skipped), otherwise most common first; "Not specified" always goes last.
    """
    table: Dict[str, Counter] = {}
    for category, project_type in rows:
        table.setdefault(category or NOT_SPECIFIED, Counter())[project_type] += 1
    if order:
        labels = [c for c in order if c in table]
    else:
        labels = sorted((c for c in table if c != NOT_SPECIFIED), key=lambda c: -sum(table[c].values()))
    if NOT_SPECIFIED in table and NOT_SPECIFIED not in labels:
        labels.append(NOT_SPECIFIED)
    return {
        "series": TYPES,
        "rows": [{"label": c, "values": {t: table[c][t] for t in TYPES}} for c in labels],
    }


def _sector_budget(records, budgets: Dict[Any, float]) -> List[Dict[str, Any]]:
    """Recorded budget (funding_amount) summed per sector, largest first."""
    totals: Dict[str, List[float]] = {}
    for r in records:
        amount = budgets.get(r.submission_id)
        if not amount:
            continue
        for sector in _vocab_terms(r.sector) or [NOT_SPECIFIED]:
            totals.setdefault(sector, []).append(amount)
    rows = [{"label": k, "amount": sum(v), "projects": len(v)} for k, v in totals.items()]
    return sorted(rows, key=lambda r: -r["amount"])[:TOP_N]


@router.get("/summary", summary="Headline figures and breakdowns for the filtered projects.")
def summary(
        filters: SubmissionFilters = Depends(),
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
) -> Dict[str, Any]:
    submissions, mitigation, adaptation = _load(db, tenant, filters)
    mit = [mitigation[s.id] for s in submissions if s.id in mitigation]
    ada = [adaptation[s.id] for s in submissions if s.id in adaptation]
    amounts = [s.funding_amount for s in submissions if s.funding_amount]

    years = Counter(s.start_date.year for s in submissions if s.start_date)
    this_year = date.today().year
    type_of = {s.id: (_vocab_terms(s.intervention_measurement) or [NOT_SPECIFIED])[0] for s in submissions}
    budgets = {s.id: s.funding_amount for s in submissions if s.funding_amount}
    return {
        "total": len(submissions),
        "by_type": _counts(_vocab_terms(s.intervention_measurement) for s in submissions),
        "by_province": _counts(_vocab_terms(_geo(s).get("province")) for s in submissions),
        "by_status": _counts(_vocab_terms(s.implementation_status) for s in submissions),
        "by_funding_type": _counts(_vocab_terms(s.funding_type) for s in submissions),
        "mitigation_sectors": _counts((_vocab_terms(m.sector) for m in mit), TOP_N),
        "adaptation_sectors": _counts((_vocab_terms(a.sector) for a in ada), TOP_N),
        "hazards": _counts((_vocab_terms(a.hazard) for a in ada), TOP_N),
        "by_start_year": [{"year": y, "count": years[y]} for y in sorted(years)],
        "start_year_unknown": sum(1 for s in submissions if not s.start_date),
        "under_way_by_year": _by_type(
            ((year, type_of[s.id]) for s in submissions for year in _years_under_way(s, this_year)),
            order=list(range(1900, this_year + 1)),
        ),
        "under_way_unknown": sum(1 for s in submissions if not s.start_date),
        "status_by_type": _by_type(
            ((_vocab_terms(s.implementation_status) or [None])[0], type_of[s.id]) for s in submissions
        ),
        "funding_type_by_type": _by_type(
            ((_vocab_terms(s.funding_type) or [None])[0], type_of[s.id]) for s in submissions
        ),
        "budget_ranges": _by_type(
            (((_vocab_terms(s.estimated_budget_cost) or [None])[0], type_of[s.id]) for s in submissions),
            order=BUDGET_RANGES,
        ),
        "sector_budget": {
            "mitigation": _sector_budget(mit, budgets),
            "adaptation": _sector_budget(ada, budgets),
        },
        "funding": {
            "total_amount": sum(amounts),
            # A few very large projects dominate the total (e.g. R86bn for one
            # green-hydrogen project), so the typical budget is reported too.
            "median_amount": median(amounts) if amounts else None,
            "projects_with_amount": len(amounts),
        },
    }


@router.get("/locations", summary="Map points for the filtered projects.")
def locations(
        filters: SubmissionFilters = Depends(),
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
) -> Dict[str, Any]:
    """
    One entry per project that has a real location, with all its points, plus
    how many projects had none (so the map can say what it leaves out).
    """
    projects, without = [], 0
    for s in filtered_submissions(db, tenant, filters).all():
        points = _points(s)
        if not points:
            without += 1
            continue
        projects.append({
            "id": str(s.id),
            "title": s.title,
            "type": s.intervention_measurement,
            "points": [[round(lat, 5), round(lon, 5)] for lat, lon in points],
        })
    return {"projects": projects, "without_location": without}


# ──────────────────────────────────────────────────────────────────────────────
# Data quality
# ──────────────────────────────────────────────────────────────────────────────

#: (key, label, test) — test(submission) is True when the field is filled in.
QUALITY_FIELDS = [
    ("title", "Title", lambda s: not _blank(s.title)),
    ("description", "Description", lambda s: not _blank(s.description)),
    ("province", "Province", lambda s: bool(_vocab_terms(_geo(s).get("province")))),
    ("coordinates", "Map location", lambda s: _coordinates(s) is not None),
    ("implementation_status", "Implementation status", lambda s: not _blank(s.implementation_status)),
    ("implementation_organization", "Implementing organisation", lambda s: not _blank(s.implementation_organization)),
    ("start_date", "Start date", lambda s: s.start_date is not None),
    ("end_date", "End date", lambda s: s.end_date is not None),
    ("funding_type", "Funding type", lambda s: not _blank(s.funding_type)),
    ("funding_amount", "Budget amount", lambda s: bool(s.funding_amount)),
    ("project_manager_name", "Project manager", lambda s: not _blank(s.project_manager_name)),
    ("project_manager_email", "Contact email", lambda s: not _blank(s.project_manager_email)),
]


def _completeness(submissions: List[Submission]) -> List[Dict[str, Any]]:
    total = len(submissions)
    return [
        {"field": key, "label": label, "filled": (filled := sum(1 for s in submissions if test(s))),
         "missing": total - filled}
        for key, label, test in QUALITY_FIELDS
    ]


def _normalise_title(title: Optional[str]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (title or "").lower()).strip()


@router.get("/quality", summary="How complete the filtered project records are, overall and per data source.")
def quality(
        filters: SubmissionFilters = Depends(),
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
) -> Dict[str, Any]:
    submissions = filtered_submissions(db, tenant, filters).all()

    by_source: Dict[str, List[Submission]] = {}
    for s in submissions:
        by_source.setdefault(s.data_source or NOT_SPECIFIED, []).append(s)

    titles = Counter(t for t in (_normalise_title(s.title) for s in submissions) if t)
    duplicate_groups = {t: n for t, n in titles.items() if n > 1}

    return {
        "total": len(submissions),
        "fields": _completeness(submissions),
        "by_source": [
            {"source": source, "total": len(rows), "fields": _completeness(rows)}
            for source, rows in sorted(by_source.items(), key=lambda kv: -len(kv[1]))
        ],
        "duplicate_titles": {
            "groups": len(duplicate_groups),
            "projects": sum(duplicate_groups.values()),
        },
    }


# ──────────────────────────────────────────────────────────────────────────────
# Export
# ──────────────────────────────────────────────────────────────────────────────

def _terms(value: Any) -> str:
    return "; ".join(_vocab_terms(value))


def _date(value) -> Optional[str]:
    return value.date().isoformat() if value else None


#: (header, value(submission, mitigation, adaptation)). Project-manager email
#: and phone are deliberately left out: the export is public, and a bulk
#: download would make personal contact details trivial to harvest.
EXPORT_COLUMNS = [
    ("Project ID", lambda s, m, a: str(s.id)),
    ("Title", lambda s, m, a: s.title),
    ("Type", lambda s, m, a: s.intervention_measurement),
    ("Description", lambda s, m, a: s.description),
    ("Implementation status", lambda s, m, a: s.implementation_status),
    ("Implementing organisation", lambda s, m, a: s.implementation_organization),
    ("Other partners", lambda s, m, a: s.implementation_partners_other),
    ("Start date", lambda s, m, a: _date(s.start_date)),
    ("End date", lambda s, m, a: _date(s.end_date)),
    ("Funding organisation", lambda s, m, a: s.funding_organization),
    ("Funding type", lambda s, m, a: s.funding_type),
    ("Budget (ZAR)", lambda s, m, a: s.funding_amount),
    ("Estimated budget range", lambda s, m, a: s.estimated_budget_cost),
    ("Province", lambda s, m, a: _terms(_geo(s).get("province"))),
    ("District", lambda s, m, a: _terms(_geo(s).get("district"))),
    ("Local municipality", lambda s, m, a: _terms(_geo(s).get("local_municipality"))),
    ("Town", lambda s, m, a: _terms(_geo(s).get("town"))),
    ("Latitude", lambda s, m, a: (_coordinates(s) or (None, None))[0]),
    ("Longitude", lambda s, m, a: (_coordinates(s) or (None, None))[1]),
    ("Project manager", lambda s, m, a: s.project_manager_name),
    ("Project manager organisation", lambda s, m, a: s.project_manager_organization),
    ("Link", lambda s, m, a: s.link),
    ("Mitigation sector", lambda s, m, a: m and _terms(m.sector)),
    ("Mitigation subsector", lambda s, m, a: m and _terms(m.subsector)),
    ("Mitigation project type", lambda s, m, a: m and _terms(m.project_type)),
    ("Mitigation programme", lambda s, m, a: m and _terms(m.mitigation_program)),
    ("Mitigation national policy", lambda s, m, a: m and _terms(m.national_policy)),
    ("Carbon credits", lambda s, m, a: m and _terms(m.carbon_credit)),
    ("Adaptation sector", lambda s, m, a: a and _terms(a.sector)),
    ("Hazards", lambda s, m, a: a and _terms(a.hazard)),
    ("Adaptation national policy", lambda s, m, a: a and _terms(a.national_policy)),
    ("Climate impact", lambda s, m, a: a and a.climate_impact),
    ("Data source", lambda s, m, a: s.data_source),
]


def _cell(value: Any) -> Any:
    """Empty cell for missing values (None, or ``m and ...`` on a project with no mitigation row)."""
    return "" if value is None or value is False else value


def _rows(submissions, mitigation, adaptation) -> Iterable[list]:
    for s in submissions:
        m, a = mitigation.get(s.id), adaptation.get(s.id)
        yield [_cell(value(s, m, a)) for _, value in EXPORT_COLUMNS]


def _csv(rows: Iterable[list]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow([h for h, _ in EXPORT_COLUMNS])
    writer.writerows(rows)
    # BOM so Excel opens the UTF-8 file with accents (e.g. "Ekurhuleni – Tembisa") intact.
    return ("﻿" + out.getvalue()).encode("utf-8")


def _xlsx(rows: Iterable[list]) -> bytes:
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Projects")
    ws.append([h for h, _ in EXPORT_COLUMNS])
    for row in rows:
        ws.append(row)
    out = io.BytesIO()
    wb.save(out)
    return out.getvalue()


@router.get("/export", summary="Download the filtered projects as an Excel or CSV file.")
def export(
        format: Literal["xlsx", "csv"] = "xlsx",
        filters: SubmissionFilters = Depends(),
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
) -> StreamingResponse:
    submissions, mitigation, adaptation = _load(db, tenant, filters)

    rows = list(_rows(submissions, mitigation, adaptation))
    if format == "csv":
        content, media_type = _csv(rows), "text/csv; charset=utf-8"
    else:
        content, media_type = _xlsx(rows), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

    # Log only once the file is built: committing expires every loaded object,
    # and reading them afterwards would re-query each project one by one.
    db.add(DownloadLog(
        submission_ids=[str(s.id) for s in submissions],
        submission_search=str(filters.as_dict()) if filters.as_dict() else None,
    ))
    db.commit()

    if filters.submission_id and len(submissions) == 1:
        # A single project's download is named after it.
        slug = re.sub(r"[^a-z0-9]+", "-", (submissions[0].title or "").lower()).strip("-")[:60] or "project"
        filename = f"nccrd-{slug}.{format}"
    else:
        filename = f"nccrd-projects-{date.today().isoformat()}.{format}"
    return StreamingResponse(
        iter([content]),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
