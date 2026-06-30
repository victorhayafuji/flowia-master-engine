"""Request/response models for the kiosk (totem) API."""
from __future__ import annotations

from pydantic import BaseModel


class TotemAdvanceRequest(BaseModel):
    session_id: str
    selection: str = ""  # option id (button/list) or free text (identification)


class TotemTurnResponse(BaseModel):
    session_id: str
    response: str
    step: dict | None = None
    done: bool = False
