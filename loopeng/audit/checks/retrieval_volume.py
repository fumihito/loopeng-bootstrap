from __future__ import annotations

from .common import AuditContext, AuditFinding
from ..policy import RETRIEVAL_VOLUME_THRESHOLD


def check_retrieval_volume(context: AuditContext) -> list[AuditFinding]:
    events = [event for event in context.events if event.get("kind") == "retrieval"]
    if not events:
        return []
    count = sum(len(event.get("read_ids", [])) for event in events if isinstance(event.get("read_ids"), list))
    if count <= RETRIEVAL_VOLUME_THRESHOLD:
        return []
    return [AuditFinding(check_id="retrieval_volume", severity="info", message="retrieval read volume exceeds policy threshold", evidence=(f"read_ids={count}", f"threshold={RETRIEVAL_VOLUME_THRESHOLD}"))]
