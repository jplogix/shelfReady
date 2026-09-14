"""Record real Strands hook events onto AgentAction rows for the activity UI."""

from __future__ import annotations

import time
from typing import Any

from app.agent.tools import get_ctx


def record_agent_event(
    event_name: str,
    *,
    success: bool = True,
    product_id: str | None = None,
    duration_ms: int | None = None,
    source_refs: list[str] | None = None,
    detail: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Persist a sanitized execution event. Never logs chain-of-thought or secrets."""
    try:
        ctx = get_ctx()
    except RuntimeError:
        return
    payload_in = {
        "event": event_name,
        "run_id": str(ctx.job.id),
        "batch_id": str(ctx.batch.id),
        "product_id": product_id,
        "agent_mode": ctx.job.agent_mode,
        "lookup_mode": (ctx.job.checkpoint or {}).get("lookup_mode"),
    }
    payload_out = {
        "duration_ms": duration_ms,
        "source_refs": source_refs or [],
        **(extra or {}),
    }
    ctx.log(
        event_name,
        payload_in,
        payload_out,
        success=success,
        evidence=detail,
    )


class ExecutionRecorder:
    """Strands hook provider that records tool and structured-output events."""

    def __init__(self) -> None:
        self._starts: dict[str, float] = {}
        self.current_product_id: str | None = None

    def register_hooks(self, registry: Any) -> None:
        from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent

        registry.add_callback(BeforeToolCallEvent, self._before_tool)
        registry.add_callback(AfterToolCallEvent, self._after_tool)

    def attach(self, agent: Any) -> None:
        try:
            agent.hooks.add_hook(self)
        except Exception:
            try:
                from strands.hooks import AfterToolCallEvent, BeforeToolCallEvent

                agent.hooks.add_callback(BeforeToolCallEvent, self._before_tool)
                agent.hooks.add_callback(AfterToolCallEvent, self._after_tool)
            except Exception:
                # Tools still log via ToolContext.log; structured-output events are recorded by runner.
                pass

    def _tool_name(self, event: Any) -> str:
        tool_use = getattr(event, "tool_use", None) or {}
        if isinstance(tool_use, dict):
            return str(tool_use.get("name") or tool_use.get("toolUseId") or "tool")
        return getattr(tool_use, "name", None) or "tool"

    def _tool_key(self, event: Any) -> str:
        tool_use = getattr(event, "tool_use", None) or {}
        if isinstance(tool_use, dict):
            return str(tool_use.get("toolUseId") or tool_use.get("name") or id(event))
        return str(getattr(tool_use, "toolUseId", None) or id(event))

    def _before_tool(self, event: Any) -> None:
        key = self._tool_key(event)
        self._starts[key] = time.perf_counter()
        record_agent_event(
            "tool_started",
            product_id=self.current_product_id,
            detail=self._tool_name(event),
            extra={"tool_name": self._tool_name(event)},
        )

    def _after_tool(self, event: Any) -> None:
        key = self._tool_key(event)
        started = self._starts.pop(key, None)
        duration = int((time.perf_counter() - started) * 1000) if started is not None else None
        result = getattr(event, "result", None) or getattr(event, "tool_result", None)
        success = True
        if isinstance(result, dict):
            success = result.get("status", "success") != "error" and not result.get("error")
        exception = getattr(event, "exception", None)
        if exception:
            success = False
        record_agent_event(
            "tool_completed" if success else "tool_failed",
            success=success,
            product_id=self.current_product_id,
            duration_ms=duration,
            detail=self._tool_name(event),
            extra={"tool_name": self._tool_name(event)},
        )

    def structured_output(self, *, success: bool, product_id: str | None, detail: str) -> None:
        record_agent_event(
            "structured_output_success" if success else "structured_output_failure",
            success=success,
            product_id=product_id,
            detail=detail,
        )

    def decision_state(self, name: str, *, product_id: str | None = None, detail: str | None = None) -> None:
        record_agent_event(name, product_id=product_id, detail=detail)
