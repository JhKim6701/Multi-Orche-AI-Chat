from __future__ import annotations

import platform

import psutil


def get_hardware_metrics() -> dict:
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    metrics = {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": vm.percent,
        "memory_used": vm.used,
        "memory_total": vm.total,
        "disk_percent": disk.percent,
        "disk_used": disk.used,
        "disk_total": disk.total,
        "gpu_available": False,
        "gpu_usage": None,
        "gpu_memory": None,
        "gpu_vendor": None,
        "platform": platform.platform(),
    }
    return metrics
