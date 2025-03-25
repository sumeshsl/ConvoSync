from pydantic import BaseModel
from typing import Optional

#Input for preprocessing model
class Query(BaseModel):
    id: Optional[int] = None
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    usercommand: str
    source: str

#Represents a response for a query from a specific AI model
class AIResponse(BaseModel):
    response: str
    model: str

#Input for Verification Service
class QueryResult(Query):
    results: list[AIResponse]

#Output from verification service
#Input to postprocessing service
class AIQueryResponse(Query):
    result: AIResponse
