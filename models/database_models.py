from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    name: str
    mail: str
    phone: str
    password: str
    socket_id: Optional[str] = ""

class Item(BaseModel):
    owner_id: Optional[str] = ""
    name: str
    state: bool # True for lost, False for found
    description: str
    image: str
