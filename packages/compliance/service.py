"""Compliance service facade."""

from __future__ import annotations

from typing import Any

from packages.compliance.consent import build_privacy_notice
from packages.compliance.erasure import erase_patient_data
from packages.compliance.export import export_patient_data


def get_privacy_notice_preview(org_name: str = "salão") -> dict[str, str]:
    from packages.compliance.consent import PRIVACY_NOTICE_VERSION

    return {
        "version": PRIVACY_NOTICE_VERSION,
        "text": build_privacy_notice(org_name),
    }


def export_data(org_id: str, patient_id: str) -> dict[str, Any]:
    return export_patient_data(org_id, patient_id)


def erase_data(org_id: str, patient_id: str) -> dict[str, Any]:
    return erase_patient_data(org_id, patient_id)
