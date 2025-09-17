"""
Health check utilities for the backup service.
"""
import os
import time
from typing import Dict, Any


class HealthChecker:
    """Health check utility for monitoring service status."""
    
    def __init__(self, log):
        self.log = log
        self.start_time = time.time()
    
    def check_health(self) -> Dict[str, Any]:
        """
        Perform comprehensive health checks.
        
        Returns:
            Dict containing health status and metrics
        """
        health_status = {
            "status": "healthy",
            "timestamp": time.time(),
            "uptime": time.time() - self.start_time,
            "checks": {}
        }
        
        # Check disk space
        try:
            backup_path = os.path.join(os.getcwd(), 'backup')
            if os.path.exists(backup_path):
                statvfs = os.statvfs(backup_path)
                free_space = statvfs.f_frsize * statvfs.f_bavail
                total_space = statvfs.f_frsize * statvfs.f_blocks
                used_space = total_space - free_space
                
                health_status["checks"]["disk_space"] = {
                    "status": "healthy" if free_space > 1024 * 1024 * 1024 else "warning",  # 1GB threshold
                    "free_gb": round(free_space / (1024**3), 2),
                    "used_gb": round(used_space / (1024**3), 2),
                    "total_gb": round(total_space / (1024**3), 2),
                    "usage_percent": round((used_space / total_space) * 100, 2)
                }
            else:
                health_status["checks"]["disk_space"] = {
                    "status": "error",
                    "message": "Backup directory not found"
                }
        except Exception as e:
            health_status["checks"]["disk_space"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Check Minecraft data directory
        try:
            mc_data_path = os.path.join(os.getcwd(), 'data')
            if os.path.exists(mc_data_path):
                health_status["checks"]["mc_data"] = {
                    "status": "healthy",
                    "path": mc_data_path,
                    "readable": os.access(mc_data_path, os.R_OK)
                }
            else:
                health_status["checks"]["mc_data"] = {
                    "status": "error",
                    "message": "Minecraft data directory not found"
                }
        except Exception as e:
            health_status["checks"]["mc_data"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Check backup files
        try:
            backup_path = os.path.join(os.getcwd(), 'backup')
            if os.path.exists(backup_path):
                backup_files = [f for f in os.listdir(backup_path) 
                              if os.path.isfile(os.path.join(backup_path, f))]
                health_status["checks"]["backup_files"] = {
                    "status": "healthy",
                    "count": len(backup_files),
                    "files": backup_files[-5:] if backup_files else []  # Last 5 files
                }
            else:
                health_status["checks"]["backup_files"] = {
                    "status": "error",
                    "message": "Backup directory not found"
                }
        except Exception as e:
            health_status["checks"]["backup_files"] = {
                "status": "error",
                "message": str(e)
            }
        
        # Determine overall status
        check_statuses = [check.get("status", "unknown") for check in health_status["checks"].values()]
        if "error" in check_statuses:
            health_status["status"] = "unhealthy"
        elif "warning" in check_statuses:
            health_status["status"] = "degraded"
        
        return health_status
    
    def get_health_summary(self) -> str:
        """Get a simple health summary string."""
        health = self.check_health()
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌"
        }
        
        emoji = status_emoji.get(health["status"], "❓")
        uptime_hours = health["uptime"] / 3600
        
        return f"{emoji} Status: {health['status'].upper()} | Uptime: {uptime_hours:.1f}h"
