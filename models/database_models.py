from pydantic import BaseModel
from typing import Optional

class User(BaseModel):
    _id: Optional[str] = ""
    name: str
    mail: str
    phone: str
    socket_id: str

class Item(BaseModel):
    _id: Optional[str] = ""
    owner_id: Optional[str] = ""
    name: str
    state: bool # True for lost, False for found
    description: str
    image: str
