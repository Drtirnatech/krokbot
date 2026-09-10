from pydantic import BaseModel

class SystemSummary(BaseModel):
    cpu_percent: float
    memory_percent: float
    os_info: str
    uptime_seconds: float

class StoragePartition(BaseModel):
    device: str
    mount_point: str
    total_gb: float
    used_gb: float
    free_gb: float
    percent_used: float

class ServiceItem(BaseModel):
    pid: int
    name: str
    status: str
    cpu_percent: float
    memory_percent: float
