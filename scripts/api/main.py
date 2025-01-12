from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from metrics import router as metrics_router
from logs import router as logs_router

app = FastAPI(title="Ghostwriter API")

# Configure CORS for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],  # Add 5174 since Vite is using it
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(metrics_router)
app.include_router(logs_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 