from fastapi import FastAPI
import postprocessing_routes

# Initialize the FastAPI app
app = FastAPI(title="AdaptAI PostProcessing", version="1.0.0")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8004)

# Include the example routes
app.include_router(postprocessing_routes.router)

# Root endpoint
@app.get("/")
def read_root():
    return {"message": "Welcome to Postprocessing API!"}
