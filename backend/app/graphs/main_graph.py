from langgraph.graph import StateGraph, START, END
from pymongo import MongoClient
from langgraph.checkpoint.mongodb import MongoDBSaver

from backend.app.graphs.state import WingmanState
from backend.app.graphs.nodes.memory_retriever import memory_retriever_node
from backend.app.graphs.nodes.planner import planner_node
from backend.app.graphs.nodes.orchestrator import orchestrator_node
from backend.app.graphs.nodes.subagents import web_agent_node, comm_agent_node, work_agent_node, rag_agent_node
from backend.app.graphs.nodes.tool_executor import tool_executor_node
from backend.app.graphs.nodes.reflection import reflection_node
from backend.app.graphs.routers.conditional import routing_decision
from backend.app.core.config import settings
from backend.app.core.logging import logger

def build_wingman_graph():
    """
    Assembles the full enterprise cognitive runtime LangGraph cyclic workflow.
    Implements strict planning boundaries, dynamic tool orchestration,
    self-reflection audits, and ACID durable MongoDB persistence.
    """
    logger.info("Scaffolding advanced Wingman Cognitive Runtime topology...")
    
    # 1. Initialize Graph with our Enterprise WingmanState
    workflow = StateGraph(WingmanState)
    
    # 2. Add System Cognitive Execution Nodes
    workflow.add_node("memory_retriever", memory_retriever_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("orchestrator", orchestrator_node)
    workflow.add_node("web_agent", web_agent_node)
    workflow.add_node("comm_agent", comm_agent_node)
    workflow.add_node("work_agent", work_agent_node)
    workflow.add_node("rag_agent", rag_agent_node)
    workflow.add_node("tool_executor", tool_executor_node) # Fallback
    workflow.add_node("reflection", reflection_node)
    
    # 3. Map Linear Bootstrapping Flow (Observe -> Plan -> Orchestrate)
    workflow.add_edge(START, "memory_retriever")
    workflow.add_edge("memory_retriever", "planner")
    workflow.add_edge("planner", "orchestrator")
    
    # 4. Define Cyclic Tool Orchestration & Finalization Routines
    workflow.add_conditional_edges(
        "orchestrator",
        routing_decision,
        {
            "web_agent": "web_agent",
            "comm_agent": "comm_agent",
            "work_agent": "work_agent",
            "rag_agent": "rag_agent",
            "tool_executor": "tool_executor",
            "reflection": "reflection" # Route to audit cycle before responding
        }
    )
    
    # 5. Route Tool Outputs back into Orchestrator for Plan Advancement
    workflow.add_edge("web_agent", "orchestrator")
    workflow.add_edge("comm_agent", "orchestrator")
    workflow.add_edge("work_agent", "orchestrator")
    workflow.add_edge("rag_agent", "orchestrator")
    workflow.add_edge("tool_executor", "orchestrator")
    
    # 6. Wire Reflection node termination
    workflow.add_edge("reflection", END)
    
    # 7. Provision ACID Durable Persistence (MongoDBSaver)
    logger.info("[Graph] Initializing durable MongoDBSaver cluster checkpointer...")
    try:
        sync_client = MongoClient(settings.MONGODB_URL)
        checkpointer = MongoDBSaver(
            client=sync_client,
            db_name=settings.MONGODB_DB_NAME,
            checkpoint_collection_name="graph_checkpoints",
            writes_collection_name="graph_writes"
        )
    except Exception as e:
        logger.error(f"FAILED provisioning durable checkpointer: {e}. Falling back to MemorySaver.", exc_info=True)
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
    
    logger.info("Compiling Cognitive Graph topology with durable checkpointer...")
    return workflow.compile(checkpointer=checkpointer)

# Export pre-compiled singleton reference
wingman_app = build_wingman_graph()
