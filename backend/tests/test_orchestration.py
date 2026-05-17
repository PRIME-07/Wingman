import os
import sys


# Force backend root into path to enable localized run commands
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def test_tool_registry_initialization():
    """Verifies all essential MVP tools populate the central registry."""
    from backend.app.tools.registry import tool_registry
    
    tools = tool_registry.list_tools()
    tool_names = [t.name for t in tools]
    
    assert "clock_utility" in tool_names, "Clock utility not found"
    assert "web_search" in tool_names, "Web search not found"
    assert "memory_retrieval" in tool_names, "Memory tool missing"
    assert "gmail_draft" in tool_names, "Gmail draft missing"
    assert "slack_draft" in tool_names, "Slack tool missing"
    assert "calendar_schedule" in tool_names, "Calendar Schedule tool missing"
    assert "calendar_query" in tool_names, "Calendar Query tool missing"
    assert "calendar_modify" in tool_names, "Calendar Modify tool missing"
    assert "calendar_delete" in tool_names, "Calendar Delete tool missing"
    
    print("\u2713 Tool Registry initialization successful.")

def test_graph_topology_compilation():
    """Verifies StateGraph topology compiles successfully with custom state structure."""
    from backend.app.graphs.main_graph import wingman_app
    
    # Assert the compiled runnable has required structures
    assert wingman_app is not None
    assert hasattr(wingman_app, "ainvoke"), "Compiled graph missing async runners."
    
    # Verify expected nodes exist in graph topology
    nodes = list(wingman_app.nodes.keys())
    assert "memory_retriever" in nodes
    assert "orchestrator" in nodes
    assert "tool_executor" in nodes
    
    print("\u2713 LangGraph operational topology compiled correctly.")

def test_openai_tool_schema_conversions():
    """Confirms serialization of tool schemas into OpenAI native JSON definitions."""
    from backend.app.tools.registry import tool_registry
    
    schemas = tool_registry.get_openai_tool_definitions()
    
    assert len(schemas) > 0
    for s in schemas:
        assert s["type"] == "function"
        assert "name" in s["function"]
        assert "description" in s["function"]
        assert "parameters" in s["function"]
        assert "properties" in s["function"]["parameters"]
        
    print("\u2713 OpenAI Function mapping validations completed successfully.")

if __name__ == "__main__":
    test_tool_registry_initialization()
    test_graph_topology_compilation()
    test_openai_tool_schema_conversions()
    print("\n[ALL UNIT VALIDATION CHECKS PASSED SUCCESSFULLY]")
