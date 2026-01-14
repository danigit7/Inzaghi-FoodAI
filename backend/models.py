from pydantic import BaseModel
from typing import List, Optional

class MenuItem(BaseModel):
    item: str
    price: int

class Restaurant(BaseModel):
    id: str
    name: str
    category: Optional[str] = None
    menu: List[MenuItem]
    deals: List[str] = []
    
    # Optional fields for backward compatibility or computed values
    cuisine: List[str] = []
    rating: Optional[float] = None
    budget: Optional[str] = None
    location: Optional[str] = None