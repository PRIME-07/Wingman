from typing import Dict, Any, Optional, Tuple
from backend.app.planner.schemas import ExecutionPlan, PlanStep, StepStatus
from backend.app.core.logging import logger

class ExecutionResilienceManager:
    """
    P4 Governance Routine overseeing retry policies, rollback activations, 
    and partial completion checkpoints during dynamic step execution.
    """

    @staticmethod
    def handle_step_failure(
        plan: Dict[str, Any], 
        step_id: str, 
        error_msg: str
    ) -> Tuple[Dict[str, Any], bool]:
        """
        Evaluates a failing step. Decides if we can retry, trigger compensating 
        action, or flag total plan halt.
        
        Returns: (Updated Plan Dictionary, Should_Retry Boolean)
        """
        try:
            exec_plan = ExecutionPlan.model_validate(plan)
        except Exception as e:
            logger.error(f"[Resilience] Invalid execution plan structure passed: {e}")
            return plan, False

        target_step: Optional[PlanStep] = None
        for s in exec_plan.steps:
            if s.step_id == step_id:
                target_step = s
                break
                
        if not target_step:
            logger.error(f"[Resilience] Step '{step_id}' not located in plan manifest.")
            return plan, False

        # Increment attempts
        target_step.retry_count += 1
        target_step.error_trace = error_msg
        
        # Check if under retry limit
        if target_step.retry_count <= target_step.max_retries:
            logger.warning(
                f"[Resilience] Step '{step_id}' failed but remaining retries available "
                f"({target_step.retry_count}/{target_step.max_retries}). Queueing RETRY."
            )
            target_step.status = StepStatus.PENDING # Re-queue
            return exec_plan.model_dump(mode="json"), True
            
        # Reached maximum retries
        logger.error(f"[Resilience] Step '{step_id}' EXHAUSTED all retries ({target_step.max_retries}). Escalating failure.")
        target_step.status = StepStatus.FAILED
        exec_plan.failure_count += 1
        
        # Check if compensating action exists
        if target_step.compensating_action:
            logger.info(f"[Resilience] Locating compensating action rollback trigger for '{step_id}': {target_step.compensating_action}")
            target_step.status = StepStatus.COMPENSATING
            exec_plan.rollback_active = True
            
            # Injects compensating action as immediate next step
            rollback_step = PlanStep(
                step_id=f"rollback-{step_id}",
                description=f"COMPENSATE: {target_step.compensating_action}",
                assigned_tool=None, # Standard LLM resolution of compensating logic
                status=StepStatus.PENDING,
                priority=target_step.priority
            )
            # Splice in directly ahead
            idx = exec_plan.steps.index(target_step)
            exec_plan.steps.insert(idx + 1, rollback_step)
            exec_plan.next_step_id = rollback_step.step_id
            
            return exec_plan.model_dump(mode="json"), False
            
        # Irrecoverable failure: Force total fallback execution path
        exec_plan.next_step_id = None
        exec_plan.is_complete = True # Halt execution traversal
        return exec_plan.model_dump(mode="json"), False

    @staticmethod
    def record_step_success(plan: Dict[str, Any], step_id: str, output: Dict[str, Any]) -> Dict[str, Any]:
        """Updates plan status and sets next pointer on successful completion."""
        try:
            exec_plan = ExecutionPlan.model_validate(plan)
        except Exception as e:
            logger.error(f"[Resilience] Plan validation failed in success recorder: {e}")
            return plan

        current_step = None
        for i, s in enumerate(exec_plan.steps):
            if s.step_id == step_id:
                s.status = StepStatus.COMPLETED
                
                import json
                if isinstance(output, dict):
                    s.output = json.dumps(output)
                elif isinstance(output, str):
                    s.output = output
                else:
                    s.output = str(output)

                
                # Advance next_step pointer
                if i + 1 < len(exec_plan.steps):
                    exec_plan.next_step_id = exec_plan.steps[i + 1].step_id
                else:
                    exec_plan.next_step_id = None
                    exec_plan.is_complete = True
                return exec_plan.model_dump(mode="json")
                
        return plan
