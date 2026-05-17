import uuid
from fastapi import APIRouter, HTTPException, status
from typing import List
from backend.app.memory.mongodb_client import mongo_client
from backend.app.schemas.sessions import SessionCreate, SessionResponse, SessionUpdate
from backend.app.schemas.chat import ChatHistoryResponse

router = APIRouter()

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_new_session(payload: SessionCreate):
    """Creates a new distinct conversational session to prevent context bleed."""
    session_id = payload.session_id or str(uuid.uuid4())
    
    try:
        session_doc = await mongo_client.create_session(
            session_id=session_id,
            session_name=payload.session_name,
            metadata=payload.metadata
        )
        return SessionResponse(**session_doc)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create session: {str(e)}"
        )

@router.get("", response_model=List[SessionResponse])
async def list_all_sessions():
    """Retrieves all active session buckets chronologically by recent updates."""
    try:
        sessions_list = await mongo_client.list_sessions()
        return [SessionResponse(**s) for s in sessions_list]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing sessions: {str(e)}"
        )

@router.get("/{session_id}", response_model=SessionResponse)
async def get_single_session(session_id: str):
    """Fetches session metadata boundary."""
    session = await mongo_client.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found."
        )
    return SessionResponse(**session)

@router.get("/{session_id}/messages", response_model=List[ChatHistoryResponse])
async def get_session_messages(session_id: str, limit: int = 100):
    """Retrieves the sequential log of transactional chat messages for a target session."""
    session = await mongo_client.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found."
        )
    
    try:
        # Fetch existing messages from ephemeral raw_chats collection
        db_messages = await mongo_client.get_session_conversations(session_id, limit=limit)
        
        # Fetch ACID-durable message state from the compiled cognitive graph checkpointer
        from backend.app.graphs.main_graph import wingman_app
        from backend.app.core.utils import extract_text_content
        from datetime import datetime, timedelta
        from backend.app.core.logging import logger

        config = {"configurable": {"thread_id": session_id}}
        graph_history = []
        try:
            state = await wingman_app.aget_state(config)
            state_messages = state.values.get("messages", [])
            
            for idx, msg in enumerate(state_messages):
                # Disambiguate actor roles expected by UI store schemas
                if msg.type == "human":
                    role = "user"
                elif msg.type == "ai":
                    role = "assistant"
                else:
                    continue
                
                # Extract robust text fragments or compound reasoning strings
                content = extract_text_content(msg.content)
                if not content or not content.strip():
                    continue
                    
                msg_time = None
                if hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
                    ts = msg.response_metadata.get("created_at")
                    if ts:
                        try:
                            msg_time = datetime.utcfromtimestamp(ts)
                        except Exception:
                            pass
                
                graph_history.append({
                    "role": role,
                    "content": content,
                    "session_id": session_id,
                    "created_at": msg_time,
                    "trace_id": getattr(msg, "id", None)
                })
        except Exception as state_err:
            logger.warning(f"[Session-Recovery] Failed to extract graph checkpoint state for session {session_id}: {state_err}")
            graph_history = []
            
        # Optimal Merge/Fallback heuristic:
        # If the checkpointer state contains strictly more conversational turns than the working collection
        # (e.g., due to historical memory consolidation runs that pre-date our raw_chats retention update),
        # reconstruct the timeline using ACID checkpoints. Otherwise, prefer raw_chats for precise timestamp fidelity.
        final_messages = []
        if len(graph_history) > len(db_messages):
            base_time = session.get("created_at") or (datetime.utcnow() - timedelta(minutes=len(graph_history)))
            
            current_anchor = base_time
            for i, m in enumerate(graph_history):
                if m["created_at"] is None:
                    # Maintain chronological sort invariant via dynamic incremental staggering
                    m["created_at"] = current_anchor + timedelta(seconds=i)
                else:
                    if m["created_at"] > current_anchor:
                        current_anchor = m["created_at"]
                final_messages.append(m)
        else:
            final_messages = db_messages

        # Finalize formatting using validated response model instances
        results = []
        for m in final_messages:
            results.append(ChatHistoryResponse(
                role=m.get("role", "assistant"),
                content=m.get("content", ""),
                session_id=m.get("session_id") or m.get("sessionID") or session_id,
                created_at=m.get("created_at") or datetime.utcnow(),
                trace_id=m.get("trace_id")
            ))
            
        return results
        
    except Exception as e:
        from backend.app.core.logging import logger
        logger.error(f"[Session-Recovery] Fatal crash during message timeline resolution: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving unified chat history: {str(e)}"
        )

@router.patch("/{session_id}", response_model=SessionResponse)
async def rename_session(session_id: str, payload: SessionUpdate):
    """Renames a target session context."""
    session = await mongo_client.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found."
        )
    
    await mongo_client.update_session_name(session_id, payload.session_name)
    # Fetch updated state
    updated = await mongo_client.get_session(session_id)
    return SessionResponse(**updated)

@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Deletes a session."""
    session = await mongo_client.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found."
        )
    
    success = await mongo_client.delete_session(session_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete session."
        )
    return {"success": True, "message": f"Successfully deleted session {session_id}"}


