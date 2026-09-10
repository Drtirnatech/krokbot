from fastapi import FastAPI
from krokbot.bridge.metrics import get_system_summary, get_storage_info, get_services_list
from krokbot.bridge.schemas import SystemSummary, StoragePartition, ServiceItem
from typing import List

app = FastAPI(title="KrokBot Host API Bridge", version="1.0.0")

@app.get("/api/v1/system/summary", response_model=SystemSummary)
def system_summary():
    return get_system_summary()

@app.get("/api/v1/system/storage", response_model=List[StoragePartition])
def storage_info():
    return get_storage_info()

@app.get("/api/v1/services/list", response_model=List[ServiceItem])
def services_list():
    return get_services_list()
