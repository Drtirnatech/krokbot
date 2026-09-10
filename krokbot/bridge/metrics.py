import psutil
import platform
import time

def get_system_summary():
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "os_info": f"{platform.system()} {platform.release()}",
        "uptime_seconds": time.time() - psutil.boot_time()
    }

def get_storage_info():
    partitions = []
    for part in psutil.disk_partitions(all=False):
        try:
            usage = psutil.disk_usage(part.mountpoint)
            partitions.append({
                "device": part.device,
                "mount_point": part.mountpoint,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": usage.percent
            })
        except PermissionError:
            continue
    return partitions

def get_services_list(limit: int = 15):
    services = []
    pids = psutil.pids()[:limit * 3]
    for pid in pids:
        try:
            proc = psutil.Process(pid)
            services.append({
                "pid": pid,
                "name": proc.name() or 'unknown',
                "status": proc.status() or 'running',
                "cpu_percent": 0.0,
                "memory_percent": round(proc.memory_percent() or 0.0, 2)
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    services.sort(key=lambda x: x['memory_percent'], reverse=True)
    return services[:limit]
