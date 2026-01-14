import json
from typing import List
from models import Restaurant

def load_data(filepath: str) -> List[Restaurant]:
    with open(filepath, 'r') as f:
        data = json.load(f)
    return [Restaurant(**item) for item in data]
