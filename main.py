from fastapi import FastAPI
from app.routes import query_routes

# Initialize the FastAPI app
app = FastAPI(title="AdaptAI API", version="1.0.0")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)

# Include the example routes
app.include_router(query_routes.router)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to AdaptAI API!"}
