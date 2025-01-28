from fastapi import APIRouter
from app.schemas import Query
from typing import List

router = APIRouter(prefix="/queries", tags=["Queries"])

# in-memory query data
queries = [
    {"id": 1, "userCommand": "Command 01", "source": "Web"},
    {"id": 2, "userCommand": "Command 02", "source": "iPhone"},
    {"id": 3, "userCommand": "Command 03", "source": "Web"}
]

# GET all items
@router.get("/", response_model=List[Query])
def get_queries():
    return queries

# GET a single item by ID
@router.get("/{query_id}", response_model=Query)
def get_query(query_id: int):
    for query in queries:
        if query["id"] == query_id:
            return query
    return {"error": "Query not found"}

# POST a new query
@router.post("/", response_model=Query)
def create_query(query: Query):
    query_dict = query.dict()
    query_dict["id"] = len(queries) + 1
    queries.append(query_dict)
    return query_dict
