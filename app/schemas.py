from pydantic import BaseModel

class Query(BaseModel):
    userCommand: str
    source: str
