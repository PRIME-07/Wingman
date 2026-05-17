from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel, Field
from datetime import datetime
import time
from backend.app.core.logging import logger

class ToolExecutionContext(BaseModel):
    """Execution metadata injected into tools during execution."""
    trace_id: str
    run_id: str
    user_timezone: str = "UTC"
    is_background: bool = False
    has_hitl_clearance: bool = False
    hitl_decision: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


def wingman_interrupt(value: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
    """
    Custom interrupt proxy enabling bubbled HITL decisions across nested agent runtimes.
    If the execution context already possesses a pre-loaded client decision, returns it directly.
    Otherwise triggers native LangGraph suspension event.
    """
    if context.hitl_decision is not None:
        logger.info(f"[WingmanInterrupt] Injecting pre-verified decision: {context.hitl_decision}")
        return context.hitl_decision
        
    from langgraph.types import interrupt as lg_interrupt
    return lg_interrupt(value)


class ToolResult(BaseModel):
    """Standardized encapsulation for tool execution outputs."""
    success: bool
    output: Any
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Operational Real-world Authenticity Metadata
    authenticity: str = "REAL"
    simulated: bool = False
    provider_connected: bool = True
    confidence_penalty: float = 0.0


class BaseWingmanTool(ABC):
    """
    Base contract and lifecycle interface for Wingman modular tools.
    Enforces schema validation, telemetry hooks, logging, and timing tracking.
    """
    name: str
    description: str
    args_schema: Optional[Type[BaseModel]] = None

    async def run(self, args: Dict[str, Any], context: ToolExecutionContext) -> ToolResult:
        """
        Wrapper entrypoint managing execution metrics, validation, and graceful recovery.
        """
        start_time = time.perf_counter()
        logger.info(f"Starting tool run: {self.name} [TraceID={context.trace_id}]")
        
        try:
            # Optional Pydantic Schema Validation
            validated_args = args
            if self.args_schema:
                validated_args = self.args_schema(**args).model_dump()
                
            # 1. Access Control & Authorization Audit
            from backend.app.tools.base.permissions import tool_permission_engine
            perm_allowed, perm_reason = tool_permission_engine.check_permission(
                tool_name=self.name,
                context={"is_background": context.is_background, "has_hitl_clearance": context.has_hitl_clearance}
            )
            if not perm_allowed:
                logger.warning(f"[Perm-Gatekeeper] Tool '{self.name}' access blocked: {perm_reason}")
                return ToolResult(
                    success=False,
                    output=None,
                    error=perm_reason,
                    duration_ms=(time.perf_counter() - start_time) * 1000.0
                )
                
            # 2. Structural Safety & Anti-Injection Audits
            from backend.app.tools.base.safety import tool_safety_validator
            safe_allowed, safe_reason = tool_safety_validator.validate(
                tool_name=self.name,
                args=validated_args
            )
            if not safe_allowed:
                logger.error(f"[Safety-Gatekeeper] Tool '{self.name}' intercepted critical risk: {safe_reason}")
                return ToolResult(
                    success=False,
                    output=None,
                    error=safe_reason,
                    duration_ms=(time.perf_counter() - start_time) * 1000.0
                )
            
            # Execute logic implemented by subclasses
            raw_output = await self._execute(validated_args, context)
            
            # Extract real-time authenticity from execution envelope
            from backend.app.authenticity.wrapper import extract_authenticity
            auth_metrics = extract_authenticity(raw_output)
            
            # Increment runtime operational quotas for real outbound calls
            if not auth_metrics.simulated:
                provider = self._get_provider_for_quota()
                if provider:
                    from backend.app.quota.governance import quota_governance
                    await quota_governance.record_usage(provider)
            
            duration = (time.perf_counter() - start_time) * 1000.0
            logger.info(f"Successfully completed tool run: {self.name} in {duration:.2f}ms [Authenticity={auth_metrics.authenticity}]")
            
            # Record running average latency metrics for cognitive planners
            if not auth_metrics.simulated:
                from backend.app.latency.tracker import latency_tracker
                await latency_tracker.record_latency(self.name, duration)
            
            return ToolResult(
                success=True,
                output=raw_output,
                duration_ms=duration,
                authenticity=auth_metrics.authenticity,
                simulated=auth_metrics.simulated,
                provider_connected=auth_metrics.provider_connected,
                confidence_penalty=auth_metrics.confidence_penalty
            )
            
        except Exception as e:
            # Allow LangGraph internal control signals (e.g., GraphInterrupt, GraphBubbleUp) to propagate out.
            # Class name reflection protects against module reloads or subclass variations.
            cls_name = type(e).__name__
            if "Interrupt" in cls_name or "BubbleUp" in cls_name:
                raise e
                
            duration = (time.perf_counter() - start_time) * 1000.0
            err_msg = str(e)
            logger.error(f"Failed tool execution for {self.name}: {err_msg}", exc_info=True)
            
            return ToolResult(
                success=False,
                output=None,
                error=err_msg,
                duration_ms=duration,
                authenticity="FAILED",
                simulated=False,
                provider_connected=False,
                confidence_penalty=1.0
            )


    def _get_provider_for_quota(self) -> Optional[str]:
        """Derives quota service provider dimension from canonical tool prefix names."""
        if self.name.startswith("slack_"):
            return "slack"
        if self.name.startswith("weather_"):
            return "weather"
        if self.name.startswith("gmail_") or self.name.startswith("calendar_") or self.name.startswith("docs_"):
            return "google"
        if self.name.startswith("maps_"):
            return "maps"
        if self.name.startswith("youtube_"):
            return "youtube"
        return None

    @abstractmethod
    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Any:
        """The core execution engine specific to each subclass."""
        pass
