from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from backend.app.tools.base.interface import BaseWingmanTool, ToolExecutionContext
from backend.app.memory.mongodb_client import mongo_client
from backend.app.core.logging import logger

class ContactsSearchInput(BaseModel):
    query: str = Field(..., description="The name or relationship alias of the contact to look up (e.g. 'dad', 'mom', 'boss', 'John Doe').")

class ContactsSearchTool(BaseWingmanTool):
    """
    Searches the Wingman contacts address book to resolve details (name, alias, email, phone).
    Use this tool when users ask to message or contact someone by relationship alias or partial name.
    """
    name = "contacts_search"
    description = "Searches the contacts directory to resolve a contact's email, phone, name, or relationship alias (e.g. 'dad', 'mom', 'boss', 'John')."
    args_schema = ContactsSearchInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        query = args["query"]
        logger.info(f"[ContactsSearchTool] Searching directory for: '{query}'")
        
        try:
            contact = await mongo_client.get_contact_by_alias_or_name(query)
            if contact:
                logger.info(f"[ContactsSearchTool] Contact resolved successfully: {contact['name']}")
                return {
                    "success": True,
                    "found": True,
                    "contact": {
                        "contact_id": contact.get("contact_id"),
                        "name": contact.get("name"),
                        "alias": contact.get("alias"),
                        "email": contact.get("email"),
                        "phone": contact.get("phone")
                    }
                }
            else:
                logger.info(f"[ContactsSearchTool] No contact matching '{query}' found.")
                return {
                    "success": True,
                    "found": False,
                    "message": f"No contact matching '{query}' was found in the address book database."
                }
        except Exception as e:
            logger.error(f"[ContactsSearchTool] Lookup failure: {e}")
            return {"success": False, "error": str(e)}


class ContactsCreateInput(BaseModel):
    name: str = Field(..., description="Full name of the contact.")
    alias: Optional[str] = Field(None, description="Optional relationship alias, e.g. 'dad', 'mom', 'boss'.")
    email: Optional[str] = Field(None, description="Email address.")
    phone: Optional[str] = Field(None, description="Phone number.")

class ContactsCreateTool(BaseWingmanTool):
    """
    Registers a new contact record inside the Wingman address book.
    """
    name = "contacts_create"
    description = "Registers a new contact record in the address book with their name, alias relationship, email, and phone number."
    args_schema = ContactsCreateInput

    async def _execute(self, args: Dict[str, Any], context: ToolExecutionContext) -> Dict[str, Any]:
        name = args["name"]
        alias = args.get("alias")
        email = args.get("email")
        phone = args.get("phone")
        
        logger.info(f"[ContactsCreateTool] Creating contact: '{name}' (alias: '{alias}', email: '{email}')")
        
        try:
            contact = await mongo_client.create_contact(
                name=name,
                alias=alias,
                email=email,
                phone=phone
            )
            return {
                "success": True,
                "contact_id": contact.get("contact_id"),
                "message": f"Successfully registered contact '{name}' in the address book."
            }
        except Exception as e:
            logger.error(f"[ContactsCreateTool] Creation failure: {e}")
            return {"success": False, "error": str(e)}
