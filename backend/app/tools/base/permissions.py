from enum import Enum
from typing import Dict, Any, Tuple, Set
from backend.app.core.logging import logger

class PermissionPolicy(Enum):
    ALLOW_ALWAYS = "allow_always"       # Native safe calculations / info retrieves
    ALLOW_BACKGROUND = "allow_bg"       # Running in non-interactive backgrounds
    REQUIRE_APPROVAL = "require_hitl"   # Mandatory human confirmation before firing
    DENY_ALL = "deny_all"               # Suspended temporarily

class ToolPermissionEngine:
    """
    Central enforcement point for system tool capabilities.
    Aligns runtime execution mandates with high-level security profiles.
    """
    def __init__(self):
        # Default hardcoded policies mapping to core safety boundaries.
        # These can be loaded from .env or dynamic DB config in the future.
        self._registry: Dict[str, PermissionPolicy] = {
            # Highly safe operations
            "google_search": PermissionPolicy.ALLOW_ALWAYS,
            "calendar_get_events": PermissionPolicy.ALLOW_ALWAYS,
            "vector_search_memories": PermissionPolicy.ALLOW_ALWAYS,
            
            # Medium-risk background friendly
            "notion_append_block": PermissionPolicy.ALLOW_BACKGROUND,
            "gmail_list_threads": PermissionPolicy.ALLOW_ALWAYS,
            
            # Mandatory Human-In-The-Loop operations (Risk of external writing/messaging)
            "slack_draft": PermissionPolicy.REQUIRE_APPROVAL,
            "gmail_draft": PermissionPolicy.REQUIRE_APPROVAL,
            "calendar_schedule": PermissionPolicy.REQUIRE_APPROVAL,
            "google_sheets_create": PermissionPolicy.REQUIRE_APPROVAL,
            "google_sheets_append": PermissionPolicy.REQUIRE_APPROVAL,
            "google_sheets_update": PermissionPolicy.REQUIRE_APPROVAL,
            "google_docs_create": PermissionPolicy.REQUIRE_APPROVAL,
            "google_docs_edit": PermissionPolicy.REQUIRE_APPROVAL
        }
        
        # Background restricted tools (cannot run outside active sessions)
        self._bg_restricted_types = {PermissionPolicy.REQUIRE_APPROVAL}

    def check_permission(self, tool_name: str, context: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Audits a tool execution directive against organizational security profiles.
        """
        policy = self._registry.get(tool_name, PermissionPolicy.ALLOW_ALWAYS)
        
        if policy == PermissionPolicy.DENY_ALL:
            return False, f"Access Violation: Tool '{tool_name}' has been globally suspended."
            
        is_background = context.get("is_background", False)
        has_hitl_clearance = context.get("has_hitl_clearance", False)
        
        # 1. Check mandatory HITL clearing
        if policy == PermissionPolicy.REQUIRE_APPROVAL:
            if not has_hitl_clearance:
                logger.warning(f"[Auth-DENIED] Blocked unauthorized execution of '{tool_name}'. Lacks interactive HITL authorization.")
                return False, f"Permission Denied: Tool '{tool_name}' requires explicit human-in-the-loop authorization."
                
        # 2. Restrict running interactive actions in background tasks
        if is_background and policy in self._bg_restricted_types:
            return False, f"Scope Conflict: Action '{tool_name}' cannot execute within non-interactive background workers."
            
        return True, ""

# Central provider instance
tool_permission_engine = ToolPermissionEngine()
