import uuid
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, status
from pydantic import BaseModel
from langchain_core.messages import HumanMessage
from langgraph.types import Command

from backend.app.schemas.chat import ChatRequest, ChatResponse
from backend.app.graphs.main_graph import wingman_app
from backend.app.core.logging import logger
from backend.app.core.utils import extract_text_content
from backend.app.graphs.execution.helpers import emit_telemetry
from backend.app.telemetry.schemas import TelemetryEventType
from backend.app.memory.mongodb_client import mongo_client
from backend.app.cognition.hierarchy import CognitiveStateHierarchy


router = APIRouter()

class ResumeRequest(BaseModel):
    thread_id: str
    decision: Dict[str, Any]

@router.post("", response_model=ChatResponse)
async def submit_chat(payload: ChatRequest):
    """
    REST execution endpoint. Initiates or continues transactional 
    conversations by mapping thread sessions to active Graph runners.
    """
    trace_id = f"tr-{uuid.uuid4().hex[:8]}"
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    thread_id = payload.metadata.get("thread_id", "default-rest-session")
    
    config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(f"[API] Chat initiated | Trace={trace_id} Thread={thread_id}")
    
    try:
        # Extract Dynamic Configuration Overrides
        selected_model = payload.metadata.get("model")
        reasoning_effort = payload.priority_tier.lower() if payload.priority_tier else None

        # Map input payload to robust WingmanState parameters
        initial_state = {
            "messages": [HumanMessage(content=payload.message)],
            "trace_id": trace_id,
            "run_id": run_id,
            "timezone": payload.metadata.get("timezone", "UTC"),
            "session_id": thread_id,
            "is_background": False,
            "has_hitl_clearance": True, # API routes default to active human interaction
            "priority_tier": payload.priority_tier,
            "config_overrides": {
                "model_name": selected_model,
                "reasoning_effort": reasoning_effort
            },
            "execution_plan": None,
            "working_memory_summary": "",
            "active_tool_calls": [],
            "cognitive_hierarchy": CognitiveStateHierarchy.initialize_default(
                trace_id=trace_id,
                run_id=run_id,
                session_id=thread_id,
                is_background=False,
                has_hitl_clearance=True
            ).model_dump(mode="json")
        }
        
        # Broadcast initiation metrics
        await emit_telemetry(initial_state, TelemetryEventType.GRAPH_STARTED)
        
        # Log message turn in dynamic MongoDB working storage
        await mongo_client.save_chat_message({
            "role": "user",
            "content": payload.message,
            "thread_id": thread_id,
            "trace_id": trace_id,
            "model": selected_model,
            "reasoning_effort": reasoning_effort
        })
        
        # Standard invocation (respects persistence threads)
        final_state = await wingman_app.ainvoke(initial_state, config=config)
        
        await emit_telemetry(final_state, TelemetryEventType.GRAPH_COMPLETED)
        
        # Capture final synthesized AIMessage and clean its content
        last_msg = final_state["messages"][-1]
        final_response_text = extract_text_content(last_msg.content)
        
        # Log finalized output
        await mongo_client.save_chat_message({
            "role": "assistant",
            "content": final_response_text,
            "thread_id": thread_id,
            "trace_id": trace_id,
            "model": selected_model,
            "reasoning_effort": reasoning_effort
        })
        
        # Priority 11: Automatic Session Naming Trigger
        import asyncio
        from backend.app.cognition.automatic_naming import automatic_naming_engine
        asyncio.create_task(automatic_naming_engine.evaluate_and_refine(thread_id))
        
        return ChatResponse(
            response=final_response_text or "[Tool Actions Processing]",
            session_id=thread_id
        )

        
    except Exception as e:
        logger.error(f"[API] Chat transactional collapse: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Graph execution error: {str(e)}"
        )

@router.post("/resume", response_model=ChatResponse)
async def resume_execution(payload: ResumeRequest):
    """
    HITL Approval route. Re-activates execution threads halted by 
    internal interrupts by passing manual command instructions back to node.
    """
    thread_id = payload.thread_id
    decision = payload.decision
    
    config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(f"[API-HITL] Resuming thread {thread_id} with decision payload.")
    
    try:
        # Inject Command(resume=...) to continue execution from the interrupt hook
        final_state = await wingman_app.ainvoke(
            Command(resume=decision),
            config=config
        )
        
        last_msg = final_state["messages"][-1]
        final_response_text = extract_text_content(last_msg.content)
        
        return ChatResponse(
            response=final_response_text or "[Execution Complete]",
            session_id=thread_id
        )
    except Exception as e:
        logger.error(f"[API-HITL] Failed resuming execution thread: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed resuming graph: {str(e)}"
        )

@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket):
    """
    Continuous bidirectional WebSocket channel supporting prompt execution,
    manual session resumes, and structured telemetry sync states.
    """
    await websocket.accept()
    logger.info("[WS] Core Chat Channel Connected.")
    
    active_thread = "ws-default-thread"
    
    try:
        async def process_completion(cfg: dict, t_id: str, r_id: str, current_thread_id: str):
            """
            Centralized post-execution interceptor. Examines if the graph successfully completed 
            or suspended on a downstream interrupt (e.g. next step in multi-step HITL).
            """
            thread_state = await wingman_app.aget_state(cfg)
            
            if thread_state.next:
                # Graph has re-suspended on downstream tool Clearances (e.g., Sheets Append after Create)
                current_interrupts = thread_state.tasks[0].interrupts if thread_state.tasks else []
                
                await websocket.send_json({
                    "event": "hitl_suspend",
                    "thread_id": current_thread_id,
                    "interrupt_details": [i.value for i in current_interrupts] if current_interrupts else []
                })
                
                await emit_telemetry(
                    {"trace_id": t_id, "run_id": r_id}, 
                    TelemetryEventType.HITL_REQUESTED,
                    payload={"details": "Execution suspended waiting for sequential tool clearance"}
                )
            else:
                # Fully resolved execution cycle
                final_msgs = thread_state.values.get("messages", [])
                if final_msgs:
                    ai_text = extract_text_content(final_msgs[-1].content)
                    
                    await websocket.send_json({
                        "event": "final_response",
                        "text": ai_text
                    })
                    
                    # Extract model configurations persisted in runtime state
                    overrides = thread_state.values.get("config_overrides", {}) or {}
                    m_name = overrides.get("model_name")
                    r_effort = overrides.get("reasoning_effort")
                    
                    # Persist finalized turn into message partition
                    await mongo_client.save_chat_message({
                        "role": "assistant",
                        "content": ai_text,
                        "thread_id": current_thread_id,
                        "trace_id": t_id,
                        "model": m_name,
                        "reasoning_effort": r_effort
                    })
                    
                    # Automatic naming evaluator
                    import asyncio
                    from backend.app.cognition.automatic_naming import automatic_naming_engine
                    asyncio.create_task(automatic_naming_engine.evaluate_and_refine(current_thread_id))
                    
                await emit_telemetry(
                    {"trace_id": t_id, "run_id": r_id}, 
                    TelemetryEventType.GRAPH_COMPLETED
                )

        while True:
            raw_input = await websocket.receive_text()
            payload = json.loads(raw_input)
            
            action = payload.get("action", "prompt") # 'prompt' or 'resume'
            thread_id = payload.get("thread_id", active_thread)
            active_thread = thread_id
            
            config = {"configurable": {"thread_id": thread_id}}
            
            trace_id = f"tr-{uuid.uuid4().hex[:8]}"
            run_id = f"run-{uuid.uuid4().hex[:8]}"
            
            if action == "prompt":
                user_text = payload.get("message", "")
                if not user_text:
                    continue
                    
                logger.info(f"[WS] Received prompt from thread {thread_id}")
                
                # Extract Dynamic Configuration Overrides from Websocket Packet
                priority_tier = payload.get("priority_tier", "MEDIUM")
                reasoning_effort = priority_tier.lower() if priority_tier else None
                selected_model = payload.get("metadata", {}).get("model")

                # Parse multi-modal image attachment if supplied by client
                image_data_uri = payload.get("image")
                if image_data_uri:
                    from backend.app.core.config import settings
                    model_to_check = (selected_model or settings.OPENAI_MODEL or "").lower()
                    is_responses_api = any(model_to_check.startswith(p) for p in ["o1", "o3", "gpt-5.4"])
                    
                    if is_responses_api:
                        # Responses API format: input_text and input_image
                        message_content = [
                            {"type": "input_text", "text": user_text},
                            {"type": "input_image", "image_url": image_data_uri}
                        ]
                    else:
                        # Standard Chat Completions format: text and image_url
                        message_content = [
                            {"type": "text", "text": user_text},
                            {"type": "image_url", "image_url": {"url": image_data_uri}}
                        ]
                    user_message = HumanMessage(content=message_content)
                else:
                    user_message = HumanMessage(content=user_text)

                graph_state = {
                    "messages": [user_message],
                    "trace_id": trace_id,
                    "run_id": run_id,
                    "timezone": payload.get("metadata", {}).get("timezone", "UTC"),
                    "user_preferences": {
                        "location": payload.get("metadata", {}).get("location")
                    },
                    "session_id": thread_id,
                    "is_background": False,
                    "has_hitl_clearance": True,
                    "priority_tier": priority_tier,
                    "config_overrides": {
                        "model_name": selected_model,
                        "reasoning_effort": reasoning_effort
                    },
                    "execution_plan": None,
                    "working_memory_summary": "",
                    "active_tool_calls": [],
                    "cognitive_hierarchy": CognitiveStateHierarchy.initialize_default(
                        trace_id=trace_id,
                        run_id=run_id,
                        session_id=thread_id,
                        is_background=False,
                        has_hitl_clearance=True
                    ).model_dump(mode="json")
                }
                
                await emit_telemetry(graph_state, TelemetryEventType.GRAPH_STARTED)
                
                # Save raw user interaction
                await mongo_client.save_chat_message({
                    "role": "user",
                    "content": user_text,
                    "thread_id": thread_id,
                    "trace_id": trace_id,
                    "model": selected_model,
                    "reasoning_effort": reasoning_effort
                })
                
                # Stream execution states
                async for event in wingman_app.astream(graph_state, config=config, stream_mode="values"):
                    # The actual token streaming happens inside orchestrator node emitting TOKEN_STREAM events
                    # Here we can notify client of completion or general status
                    pass
                    
                # Intercept execution result to verify next state boundaries
                await process_completion(config, trace_id, run_id, thread_id)


            elif action == "resume":
                decision = payload.get("decision", {})
                logger.info(f"[WS] Resuming thread {thread_id} via web socket command.")
                
                # Resume runner
                async for event in wingman_app.astream(Command(resume=decision), config=config, stream_mode="values"):
                    pass
                    
                # Broadcast human clear signal and intercept sequential downstream states
                await emit_telemetry(
                    {"trace_id": trace_id, "run_id": run_id},
                    TelemetryEventType.HITL_RESOLVED,
                    payload={"approved": decision.get("approved", False)}
                )
                
                await process_completion(config, trace_id, run_id, thread_id)
                
    except WebSocketDisconnect:
        logger.info("[WS] Core Chat Channel Closed.")
    except Exception as e:
        logger.error(f"[WS] Channel transaction failed: {e}", exc_info=True)
        try:
            await websocket.close()
        except:
            pass
