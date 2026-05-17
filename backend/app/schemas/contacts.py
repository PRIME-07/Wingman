from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List

class ContactCreate(BaseModel):
    name: str = Field(..., description="Full name of the contact")
    alias: Optional[str] = Field(None, description="Relationship alias, ex: dad, mom, boss, etc.")
    email: Optional[str] = Field(None, description="Email address of the contact")
    phone: Optional[str] = Field(None, description="Phone number of the contact")

class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, description="Full name of the contact")
    alias: Optional[str] = Field(None, description="Relationship alias, ex: dad, mom, boss, etc.")
    email: Optional[str] = Field(None, description="Email address of the contact")
    phone: Optional[str] = Field(None, description="Phone number of the contact")

class ContactResponse(BaseModel):
    contact_id: str
    name: str
    alias: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    created_at: datetime
