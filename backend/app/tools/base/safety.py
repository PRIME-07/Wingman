import re
from typing import Dict, Any, Tuple, List
from backend.app.core.logging import logger

class ToolSafetyValidator:
    """
    Enterprise-grade guardrail for external tool invocation inputs.
    Detects injection payloads, system path manipulation attempts, 
    and semantic boundary violations prior to execution.
    """
    def __init__(self):
        # Regex for standard injection attempts (Shell commands, OS files, sensitive descriptors)
        self._injection_patterns = [
            re.compile(r"(;|\||&&|\|\||>|<)\s*(rm|del|cat|type|ls|dir|wget|curl|sh|bash|powershell|cmd)\b", re.IGNORECASE),
            re.compile(r"(/etc/passwd|/etc/shadow|windows/system32|boot\.ini)", re.IGNORECASE),
            re.compile(r"(\.\./\.\./|\.\.\\\.\.\\)", re.IGNORECASE) # Directory traversal
        ]
        
    def validate(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Performs structural, lexicographical and semantic audits on runtime parameters.
        Returns: (is_safe: bool, error_reason: str)
        """
        logger.debug(f"[Safety] Scanning payload for tool: '{tool_name}'")
        
        # Convert all string values to single inspection block to speed up scan
        inspection_string = ""
        for key, val in self._flatten_args(args).items():
            if isinstance(val, str):
                inspection_string += f" {val}"
                
        # 1. Structural and Command Injection Scan
        for pattern in self._injection_patterns:
            if pattern.search(inspection_string):
                logger.warning(f"[Safety-VIOLATION] High-Risk command/injection pattern detected in tool: {tool_name}")
                return False, "Parameter safety scan failed. Suspicious shell sequences or system references detected."

        # 2. Semantic Boundary Validations
        # Tool-specific rule engine
        if tool_name == "gmail_send_message" or tool_name == "gmail_draft_message":
            recipients = args.get("to", [])
            if isinstance(recipients, list) and len(recipients) > 10:
                return False, "Safety Boundary Violation: Limit of 10 recipients exceeded on single draft."
                
        if tool_name == "google_search":
            num_results = args.get("num", 0)
            if num_results > 50:
                return False, "Safety Boundary Violation: Maximum search result quantity capped at 50 items."

        return True, ""

    def _flatten_args(self, d: Any, parent_key: str = '', sep: str = '_') -> Dict[str, Any]:
        """Recursively flattens dictionary to evaluate nested parameters."""
        items = {}
        if not isinstance(d, dict):
            return {"_val": d}
            
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(self._flatten_args(v, new_key, sep=sep))
            elif isinstance(v, list):
                for idx, list_item in enumerate(v):
                    items.update(self._flatten_args(list_item, f"{new_key}_{idx}", sep=sep))
            else:
                items[new_key] = v
        return items

# Central provider instance
tool_safety_validator = ToolSafetyValidator()
