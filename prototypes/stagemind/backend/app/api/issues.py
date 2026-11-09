"""问题看板：创建、查询与状态流转。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.schemas import IssueCreate, IssueOut, IssueUpdate
from app.models import Issue, _utcnow

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("", response_model=list[IssueOut])
def list_issues(status: str | None = None, db: Session = Depends(get_db)) -> list[Issue]:
    stmt = select(Issue).order_by(Issue.created_at.desc())
    if status:
        stmt = stmt.where(Issue.status == status)
    return list(db.scalars(stmt))


@router.post("", response_model=IssueOut, status_code=201)
def create_issue(payload: IssueCreate, db: Session = Depends(get_db)) -> Issue:
    issue = Issue(**payload.model_dump())
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.patch("/{issue_id}", response_model=IssueOut)
def update_issue_status(
    issue_id: int, payload: IssueUpdate, db: Session = Depends(get_db)
) -> Issue:
    issue = db.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status_code=404, detail="issue not found")
    issue.status = payload.status
    issue.resolved_at = _utcnow() if payload.status == "resolved" else None
    db.commit()
    db.refresh(issue)
    return issue
