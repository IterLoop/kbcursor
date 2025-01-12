from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from metrics import router as metrics_router
from logs import router as logs_router
from data import router as data_router

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(metrics_router, prefix="/api/v1/metrics", tags=["metrics"])
app.include_router(logs_router, prefix="/api/v1/logs", tags=["logs"])
app.include_router(data_router, prefix="/api/v1/data", tags=["data"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 