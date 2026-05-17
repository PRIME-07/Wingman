from typing import Any, List, Dict, Union

def extract_text_content(content: Union[str, List[Union[str, Dict[str, Any]]]]) -> str:
    """
    Extracts raw text from potential complex/nested LangChain AIMessage structures,
    such as string, list of strings, or list of dictionaries (e.g., for Response API).
    """
    if not content:
        return ""
        
    if isinstance(content, str):
        return content
        
    if isinstance(content, list):
        text_parts = []
        for block in content:
            if isinstance(block, str):
                text_parts.append(block)
            elif isinstance(block, dict):
                # Check common text keys like 'text' or 'content'
                if "text" in block:
                    text_parts.append(str(block["text"]))
                elif "content" in block and isinstance(block["content"], str):
                    text_parts.append(block["content"])
        return "".join(text_parts)
        
    return str(content)
