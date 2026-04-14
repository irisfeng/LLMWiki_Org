from pydantic import BaseModel
from datetime import datetime
from uuid import UUID


class SourceTextSubmit(BaseModel):
    text: str
    title: str = ""
    submitted_by: str = ""

class SourceURLSubmit(BaseModel):
    url: str
    submitted_by: str = ""

class SourceResponse(BaseModel):
    id: UUID
    filename: str
    file_path: str | None = None
    status: str
    error_message: str | None = None
    submitted_by: str | None
    created_at: datetime
    processed_at: datetime | None

    model_config = {"from_attributes": True}


class WikiPageSummary(BaseModel):
    id: UUID
    type: str
    slug: str
    title: str
    frontmatter: dict
    updated_at: datetime

    model_config = {"from_attributes": True}

class WikiPageDetail(BaseModel):
    id: UUID
    type: str
    slug: str
    title: str
    frontmatter: dict
    content: str
    created_at: datetime
    updated_at: datetime
    backlinks: list[WikiPageSummary] = []

    model_config = {"from_attributes": True}

class WikiSearchResult(BaseModel):
    slug: str
    title: str
    type: str
    snippet: str

class ChatMessageCreate(BaseModel):
    content: str
    session_id: UUID | None = None
    user_name: str = ""

class ChatMessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: str
    content: str
    referenced_pages: list[str] | None
    created_at: datetime

    model_config = {"from_attributes": True}

class LintReportResponse(BaseModel):
    id: UUID
    issues: dict
    auto_fixed: int
    pending_review: int
    created_at: datetime

    model_config = {"from_attributes": True}
