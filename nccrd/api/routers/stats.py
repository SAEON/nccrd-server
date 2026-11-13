"""
Visitor numbers: page views per site and day, downloads and logins.

The web interface reports each public page it shows (POST /stats/view). Only
a count per site, day and page is kept: no visitor is identified, and no IP
address, cookie or account is recorded with a view.
"""
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import Date, cast, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from nccrd.api.lib.auth import Authorized
from nccrd.api.lib.permissions import RequirePermission
from nccrd.api.lib.tenant import get_current_tenant, site_name
from nccrd.db import get_db
from nccrd.db.models import Submission
from nccrd.db.models.rbac import DownloadLog, Login, PageView, Tenant

router = APIRouter()

#: Days are South African days.
_TZ = ZoneInfo("Africa/Johannesburg")

#: The public pages counted, by path within a site, and their names.
PAGES = {
    "/": "Home (project search)",
    "/reports": "Data reports",
    "/about": "About",
    "/register": "Request an account",
    "/login": "Log in",
    "/terms-of-use": "Terms of use",
    "/paia-popia": "PAIA & POPIA",
    "/license": "Licence",
}
_PROJECT = re.compile(r"^/submission/([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$")


def counted_path(path: str) -> Optional[str]:
    """The page to count ``path`` as, or None for pages not counted (admin pages, forms)."""
    path = (path or "").split("?")[0].split("#")[0].lower()
    path = path.rstrip("/") or "/"
    if path in PAGES or _PROJECT.match(path):
        return path
    return None


def _today() -> date:
    return datetime.now(_TZ).date()


class PageViewIn(BaseModel):
    path: str = Field(..., max_length=200, description="The page's path within the site, e.g. /reports.")


@router.post(
    "/view",
    status_code=204,
    summary="Count one view of a public page of the current site.",
)
def count_view(
        body: PageViewIn,
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
) -> Response:
    path = counted_path(body.path)
    if path is not None:
        db.execute(
            insert(PageView)
            .values(tenant_id=tenant.id, day=_today(), path=path, views=1)
            .on_conflict_do_update(
                index_elements=[PageView.tenant_id, PageView.day, PageView.path],
                set_={"views": PageView.views + 1},
            )
        )
        db.commit()
    return Response(status_code=204)


class DayCount(BaseModel):
    day: date
    views: int
    downloads: int


class PageCount(BaseModel):
    path: str
    name: str
    views: int


class SiteCount(BaseModel):
    name: str
    views: int


class Stats(BaseModel):
    since: date
    until: date
    views: int
    downloads: int
    people_logged_in: int = Field(..., description="Different people who logged in (on any site).")
    days: List[DayCount]
    pages: List[PageCount]
    projects: List[PageCount]
    sites: List[SiteCount] = Field(..., description="Views per site; on the national site only.")


@router.get(
    "",
    response_model=Stats,
    summary="The current site's page views and downloads per day, its most viewed pages and projects.",
)
def get_stats(
        days: int = Query(30, ge=7, le=366),
        db: Session = Depends(get_db),
        tenant: Tenant = Depends(get_current_tenant),
        auth: Authorized = Depends(RequirePermission("view-stats")),
) -> Stats:
    until = _today()
    since = until - timedelta(days=days - 1)
    in_range = (PageView.day >= since, PageView.day <= until)
    here = (PageView.tenant_id == tenant.id, *in_range)

    views_by_day: Dict[date, int] = dict(
        db.query(PageView.day, func.sum(PageView.views)).filter(*here).group_by(PageView.day)
    )
    download_day = cast(func.timezone("Africa/Johannesburg", func.timezone("UTC", DownloadLog.timestamp)), Date)
    downloads_by_day: Dict[date, int] = dict(
        db.query(download_day, func.count())
        .filter(DownloadLog.tenant_id == tenant.id, download_day >= since, download_day <= until)
        .group_by(download_day)
    )
    by_path = db.query(PageView.path, func.sum(PageView.views)).filter(*here).group_by(PageView.path).all()

    pages = sorted(
        (PageCount(path=p, name=PAGES[p], views=v) for p, v in by_path if p in PAGES),
        key=lambda c: -c.views,
    )
    project_views = sorted(((p, v) for p, v in by_path if p not in PAGES), key=lambda pv: -pv[1])[:10]
    ids = [UUID(_PROJECT.match(p).group(1)) for p, _ in project_views]
    titles = {s.id: s.title for s in db.query(Submission.id, Submission.title).filter(Submission.id.in_(ids))} if ids else {}
    projects = [
        PageCount(path=p, name=titles.get(UUID(_PROJECT.match(p).group(1)), "A removed project"), views=v)
        for p, v in project_views
    ]

    sites = []
    if tenant.is_default:
        per_site = dict(db.query(PageView.tenant_id, func.sum(PageView.views)).filter(*in_range).group_by(PageView.tenant_id))
        sites = sorted(
            (SiteCount(name=site_name(t), views=per_site.get(t.id, 0)) for t in db.query(Tenant)),
            key=lambda c: -c.views,
        )

    login_day = cast(func.timezone("Africa/Johannesburg", func.timezone("UTC", Login.timestamp)), Date)
    people = db.query(func.count(func.distinct(Login.user_id))).filter(login_day >= since, login_day <= until).scalar()

    every_day = [since + timedelta(days=i) for i in range(days)]
    return Stats(
        since=since,
        until=until,
        views=sum(views_by_day.values()),
        downloads=sum(downloads_by_day.values()),
        people_logged_in=people or 0,
        days=[DayCount(day=d, views=views_by_day.get(d, 0), downloads=downloads_by_day.get(d, 0)) for d in every_day],
        pages=pages,
        projects=projects,
        sites=sites,
    )
