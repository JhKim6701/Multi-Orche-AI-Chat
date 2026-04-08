from __future__ import annotations

import platform
import subprocess

import psutil

from app.services.runtime_state import get_gpu_enabled


def _read_nvidia_metrics() -> tuple[bool, float | None, float | None, str | None]:
    try:
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used,memory.total,name",
            "--format=csv,noheader,nounits",
        ]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True, timeout=1.2).strip()
        if not output:
            return False, None, None, None
        util, mem_used, mem_total, name = [p.strip() for p in output.split(",")[:4]]
        usage = float(util)
        mem_percent = (float(mem_used) / max(float(mem_total), 1.0)) * 100.0
        return True, usage, mem_percent, name
    except Exception:
        return False, None, None, None


def get_hardware_metrics() -> dict:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    gpu_available, gpu_usage, gpu_memory, gpu_vendor = _read_nvidia_metrics()
    metrics = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": vm.percent,
        "memory_used": vm.used,
        "memory_total": vm.total,
        "disk_percent": disk.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "gpu_available": gpu_available,
        "gpu_usage": gpu_usage,
        "gpu_memory": gpu_memory,
        "gpu_vendor": gpu_vendor,
        "gpu_enabled": get_gpu_enabled(),
        "platform": platform.platform(),
    }
    return metrics
