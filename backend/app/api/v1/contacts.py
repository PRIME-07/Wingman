from fastapi import APIRouter, HTTPException, status
from typing import List
from backend.app.memory.mongodb_client import mongo_client
from backend.app.schemas.contacts import ContactCreate, ContactResponse, ContactUpdate

router = APIRouter()

@router.post("", response_model=ContactResponse, status_code=status.HTTP_201_CREATED)
async def create_new_contact(payload: ContactCreate):
    """Registers a new contact in the Wingman address book database."""
    try:
        contact_doc = await mongo_client.create_contact(
            name=payload.name,
            alias=payload.alias,
            email=payload.email,
            phone=payload.phone
        )
        return ContactResponse(**contact_doc)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not create contact: {str(e)}"
        )

@router.get("", response_model=List[ContactResponse])
async def list_all_contacts():
    """Retrieves all registered address book contacts sorted alphabetically by name."""
    try:
        contacts_list = await mongo_client.list_contacts()
        return [ContactResponse(**c) for c in contacts_list]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error listing contacts: {str(e)}"
        )

@router.get("/{contact_id}", response_model=ContactResponse)
async def get_single_contact(contact_id: str):
    """Fetches a specific contact record by its unique ID."""
    contact = await mongo_client.get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact {contact_id} not found."
        )
    return ContactResponse(**contact)

@router.patch("/{contact_id}", response_model=ContactResponse)
async def update_existing_contact(contact_id: str, payload: ContactUpdate):
    """Updates one or more fields of a target contact."""
    contact = await mongo_client.get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact {contact_id} not found."
        )
    try:
        updated = await mongo_client.update_contact(contact_id, payload.dict(exclude_unset=True))
        return ContactResponse(**updated)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update contact: {str(e)}"
        )

@router.delete("/{contact_id}")
async def delete_existing_contact(contact_id: str):
    """Deletes a contact record permanently from the address book database."""
    contact = await mongo_client.get_contact(contact_id)
    if not contact:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Contact {contact_id} not found."
        )
    success = await mongo_client.delete_contact(contact_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete contact."
        )
    return {"success": True, "message": f"Successfully deleted contact {contact_id}"}
