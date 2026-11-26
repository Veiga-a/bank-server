from pydantic import BaseModel, ConfigDict, Field
from datetime import date, datetime

import enum
import uuid

class UserCreate(BaseModel):
    first_name: str
    last_name: str
    email: str
    password: str
    date_of_birth: date
    phone_number: str
    country_code: str
    address_line: str
    city: str
    postal_code: str

class UserRead(BaseModel):
    id: uuid.UUID
    first_name: str
    last_name: str
    email: str
    date_of_birth: date
    phone_number: str | None
    country_code: str
    address_line: str
    city: str
    postal_code: str
    status: enum.Enum
    created_at: datetime
    updated_at: datetime