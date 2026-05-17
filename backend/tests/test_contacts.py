import os
import sys
import asyncio
from httpx import AsyncClient, ASGITransport

# Force backend root into path to enable localized run commands
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from backend.app.memory.mongodb_client import mongo_client
from backend.app.tools.contacts.tool import ContactsSearchTool, ContactsCreateTool
from backend.app.tools.base.interface import ToolExecutionContext
from backend.app.main import app

async def test_contacts_mongodb_operations():
    """Verifies that all contact CRUD methods run correctly on the MongoDB client."""
    mongo_client.connect()
    
    # 1. Create a test contact
    test_contact = await mongo_client.create_contact(
        name="John Doe",
        alias="dad",
        email="john.doe@example.com",
        phone="+919876543210"
    )
    
    assert test_contact is not None
    contact_id = test_contact["contact_id"]
    assert contact_id is not None
    assert test_contact["name"] == "John Doe"
    assert test_contact["alias"] == "dad"
    assert test_contact["email"] == "john.doe@example.com"
    assert test_contact["phone"] == "+919876543210"
    
    # 2. Get contact by ID
    fetched = await mongo_client.get_contact(contact_id)
    assert fetched is not None
    assert fetched["name"] == "John Doe"
    
    # 3. Get contact by alias
    by_alias = await mongo_client.get_contact_by_alias_or_name("dad")
    assert by_alias is not None
    assert by_alias["contact_id"] == contact_id
    
    # 4. Get contact by case-insensitive name
    by_name = await mongo_client.get_contact_by_alias_or_name("JOHN DOE")
    assert by_name is not None
    assert by_name["contact_id"] == contact_id
    
    # 5. List contacts
    contacts_list = await mongo_client.list_contacts()
    assert len(contacts_list) >= 1
    assert any(c["contact_id"] == contact_id for c in contacts_list)
    
    # 6. Update contact
    updated = await mongo_client.update_contact(contact_id, {"email": "john.updated@example.com", "alias": "father"})
    assert updated is not None
    assert updated["email"] == "john.updated@example.com"
    assert updated["alias"] == "father"
    
    # 7. Delete contact
    delete_success = await mongo_client.delete_contact(contact_id)
    assert delete_success is True
    
    # 8. Confirm deletion
    deleted = await mongo_client.get_contact(contact_id)
    assert deleted is None


async def test_contacts_api_endpoints():
    """Exercises the FastAPI endpoints for contacts CRUD lifecycle."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create a contact
        payload = {
            "name": "Jane Doe",
            "alias": "mom",
            "email": "jane.doe@example.com",
            "phone": "+919876543211"
        }
        res_create = await ac.post("/api/v1/contacts", json=payload)
        assert res_create.status_code == 201
        data = res_create.json()
        contact_id = data["contact_id"]
        assert data["name"] == "Jane Doe"
        assert data["alias"] == "mom"
        
        # Get contact by ID
        res_get = await ac.get(f"/api/v1/contacts/{contact_id}")
        assert res_get.status_code == 200
        assert res_get.json()["name"] == "Jane Doe"
        
        # List all contacts
        res_list = await ac.get("/api/v1/contacts")
        assert res_list.status_code == 200
        contacts = res_list.json()
        assert len(contacts) >= 1
        assert any(c["contact_id"] == contact_id for c in contacts)
        
        # Patch/update contact
        res_patch = await ac.patch(f"/api/v1/contacts/{contact_id}", json={"phone": "+919999999999"})
        assert res_patch.status_code == 200
        assert res_patch.json()["phone"] == "+919999999999"
        
        # Delete contact
        res_del = await ac.delete(f"/api/v1/contacts/{contact_id}")
        assert res_del.status_code == 200
        assert res_del.json()["success"] is True
        
        # Verify 404 on deleted contact
        res_get_deleted = await ac.get(f"/api/v1/contacts/{contact_id}")
        assert res_get_deleted.status_code == 404


async def test_contacts_tool_execution():
    """Verifies that ContactsSearchTool and ContactsCreateTool resolve parameters properly."""
    # Seed a contact first
    mongo_client.connect()
    seed_contact = await mongo_client.create_contact(
        name="Alice Smith",
        alias="boss",
        email="alice.smith@example.com",
        phone="+1234567890"
    )
    contact_id = seed_contact["contact_id"]
    
    # Initialize execution context
    context = ToolExecutionContext(
        trace_id="test-trace",
        run_id="test-run"
    )
    
    # 1. Test ContactsSearchTool
    search_tool = ContactsSearchTool()
    search_res = await search_tool.run({"query": "boss"}, context=context)
    
    assert search_res.success is True
    assert search_res.output["found"] is True
    assert search_res.output["contact"]["name"] == "Alice Smith"
    assert search_res.output["contact"]["email"] == "alice.smith@example.com"
    
    # Test fallback
    not_found_res = await search_tool.run({"query": "non-existent-alias"}, context=context)
    assert not_found_res.success is True
    assert not_found_res.output["found"] is False
    
    # 2. Test ContactsCreateTool
    create_tool = ContactsCreateTool()
    create_res = await create_tool.run(
        {
            "name": "Bob Smith",
            "alias": "brother",
            "email": "bob@example.com"
        },
        context=context
    )
    
    assert create_res.success is True
    created_id = create_res.output["contact_id"]
    assert created_id is not None
    
    # Cleanup contacts
    await mongo_client.delete_contact(contact_id)
    await mongo_client.delete_contact(created_id)


if __name__ == "__main__":
    async def run_all_tests():
        print("Starting Contacts Integration tests...")
        await test_contacts_mongodb_operations()
        print("\u2713 MongoDB client CRUD operations verified successfully.")
        await test_contacts_api_endpoints()
        print("\u2713 FastAPI CRUD endpoints verified successfully.")
        await test_contacts_tool_execution()
        print("\u2713 LangChain Contacts Tools resolution verified successfully.")
        print("\n[ALL CONTACTS INTEGRATION TESTS PASSED SUCCESSFULLY]")
        
    asyncio.run(run_all_tests())
