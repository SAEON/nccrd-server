"""
Emails telling people what happened to their account request or project.
Each function queues the email as a background task (see ``nccrd.api.lib.mail``).
"""

from typing import List, Optional

from fastapi import BackgroundTasks

from nccrd.api.lib.mail import send_mail
from nccrd.api.lib.tenant import site_name
from nccrd.db.models.rbac import Tenant, User
from nccrd.db.models.submission import Submission


def _sign_off(tenant: Tenant) -> str:
    return tenant.title or site_name(tenant)


def _contact(tenant: Tenant) -> str:
    return f" at {tenant.contact_email}" if tenant.contact_email else ""


def registration_approved(background: BackgroundTasks, user: User, tenant: Tenant, address: Optional[str]) -> None:
    name = site_name(tenant)
    login = f"Log in at {address}/login with the email address and password you signed up with." if address else (
        "You can log in with the email address and password you signed up with.")
    background.add_task(
        send_mail,
        user.email,
        f"Your {name} account is ready",
        f"Hello {user.name},\n\n"
        f"Your request for an account on {name} has been approved.\n"
        f"{login}\n\n"
        f"{_sign_off(tenant)}\n",
        sender_name=name,
    )


def registration_rejected(background: BackgroundTasks, user: User, tenant: Tenant) -> None:
    name = site_name(tenant)
    background.add_task(
        send_mail,
        user.email,
        f"Your {name} account request",
        f"Hello {user.name},\n\n"
        f"Your request for an account on {name} was not approved.\n"
        f"If you think this is a mistake, contact the {name} team{_contact(tenant)}.\n\n"
        f"{_sign_off(tenant)}\n",
        sender_name=name,
    )


def submission_reviewed(
        background: BackgroundTasks,
        submitter: User,
        submission: Submission,
        tenant: Tenant,
        address: Optional[str],
        accepted: bool,
) -> None:
    name = site_name(tenant)
    page = f"\n\nSee the project at {address}/submission/{submission.id}" if address else ""
    if accepted:
        subject = f"Your project is published on {name}"
        outcome = f"Your project \"{submission.title}\" has been accepted and is now published on {name}."
    else:
        subject = f"Your project on {name} needs changes"
        outcome = (
            f"Your project \"{submission.title}\" was not accepted yet. The reviewer's comments:\n\n"
            f"{submission.submission_comments}\n\n"
            "Edit the project to make these changes; it goes back for review when you save it."
        )
    background.add_task(
        send_mail,
        submitter.email,
        subject,
        f"Hello {submitter.name},\n\n{outcome}{page}\n\n{_sign_off(tenant)}\n",
        sender_name=name,
    )


# ── Alerts for the people who run a site ─────────────────────────────────────


def account_requested(
        background: BackgroundTasks, admins: List[User], person: User, tenant: Tenant, address: Optional[str],
) -> None:
    name = site_name(tenant)
    where = f"\n\nReview it at {address}/admin/registrations" if address else ""
    note = f"\nWhy they need it: {person.registration_note}" if person.registration_note else ""
    for admin in admins:
        background.add_task(
            send_mail,
            admin.email,
            f"New account request on {name}",
            f"Hello {admin.name},\n\n"
            f"{person.name} ({person.email}, {person.organisation}) asked for an account on {name}.{note}{where}\n\n"
            f"{_sign_off(tenant)}\n",
            sender_name=name,
        )


def awaiting_review(
        background: BackgroundTasks,
        reviewers: List[User],
        tenant: Tenant,
        address: Optional[str],
        titles: List[str],
        changed: bool = False,
) -> None:
    """Tell a site's reviewers that projects are waiting: one email per batch, e.g. a bulk upload."""
    name = site_name(tenant)
    if len(titles) == 1:
        subject = f"A project is waiting for review on {name}"
        what = f"The project \"{titles[0]}\" was {'changed' if changed else 'submitted'} and is waiting for review."
    else:
        subject = f"{len(titles)} projects are waiting for review on {name}"
        listed = "\n".join(f"- {t}" for t in titles[:20])
        more = f"\n- and {len(titles) - 20} more" if len(titles) > 20 else ""
        what = f"{len(titles)} projects were submitted and are waiting for review:\n\n{listed}{more}"
    where = f"\n\nReview them at {address}/review" if address else ""
    for reviewer in reviewers:
        background.add_task(
            send_mail,
            reviewer.email,
            subject,
            f"Hello {reviewer.name},\n\n{what}{where}\n\n{_sign_off(tenant)}\n",
            sender_name=name,
        )
