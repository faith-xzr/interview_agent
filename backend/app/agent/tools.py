from datetime import datetime
from time import perf_counter
from typing import Any, Optional
from uuid import uuid4

from app.schemas import ToolCallRecord


class ToolRecorder:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.records: list[ToolCallRecord] = []

    def call(
        self,
        tool_name: str,
        stage: str,
        *,
        candidate_id: Optional[str] = None,
        input_summary: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> "_ToolCallContext":
        return _ToolCallContext(
            recorder=self,
            tool_name=tool_name,
            stage=stage,
            candidate_id=candidate_id,
            input_summary=input_summary,
            metadata=metadata or {},
        )


class _ToolCallContext:
    def __init__(
        self,
        *,
        recorder: ToolRecorder,
        tool_name: str,
        stage: str,
        candidate_id: Optional[str],
        input_summary: str,
        metadata: dict[str, Any],
    ) -> None:
        self.recorder = recorder
        self.tool_name = tool_name
        self.stage = stage
        self.candidate_id = candidate_id
        self.input_summary = input_summary
        self.metadata = metadata
        self.call_id = f"tool-{uuid4().hex}"
        self.started_at = datetime.utcnow()
        self._started_perf = 0.0
        self._output_summary = ""

    @property
    def record(self) -> ToolCallRecord:
        if not self.recorder.records:
            raise RuntimeError("Tool call has not finished yet.")
        return self.recorder.records[-1]

    def set_output_summary(self, summary: str) -> None:
        self._output_summary = summary

    def __enter__(self) -> "_ToolCallContext":
        self._started_perf = perf_counter()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        completed_at = datetime.utcnow()
        duration_ms = int(max(0, (perf_counter() - self._started_perf) * 1000))
        status = "failed" if exc is not None else "success"
        record = ToolCallRecord(
            call_id=self.call_id,
            tool_name=self.tool_name,
            stage=self.stage,
            status=status,
            run_id=self.recorder.run_id,
            candidate_id=self.candidate_id,
            input_summary=self.input_summary,
            output_summary=self._output_summary,
            error_message=str(exc) if exc is not None else None,
            started_at=self.started_at,
            completed_at=completed_at,
            duration_ms=duration_ms,
            metadata=self.metadata,
        )
        self.recorder.records.append(record)
        return False
