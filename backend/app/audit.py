import json
import logging
from typing import Any, List, Optional

from app.schemas import AuditEvent

logger = logging.getLogger("app.audit")


def record_audit_event(
    audit_events: List[AuditEvent],
    *,
    event: str,
    stage: str,
    failure_code: str,
    message: str,
    fallback_strategy: str,
    run_id: Optional[str] = None,
    candidate_id: Optional[str] = None,
    model: Optional[str] = None,
    prompt_version: Optional[str] = None,
    invalid_requirements: Optional[List[str]] = None,
    details: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    audit_event = AuditEvent(
        event=event,
        stage=stage,
        failure_code=failure_code,
        message=message,
        fallback_strategy=fallback_strategy,
        run_id=run_id,
        candidate_id=candidate_id,
        model=model,
        prompt_version=prompt_version,
        invalid_requirements=invalid_requirements or [],
        details=details or {},
    )
    audit_events.append(audit_event)
    logger.warning(json.dumps(audit_event.model_dump(mode="json"), ensure_ascii=False, sort_keys=True))
    return audit_event
