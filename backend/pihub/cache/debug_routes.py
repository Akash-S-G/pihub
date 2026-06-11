"""
Monitoring and Debug API Endpoints

Exposes:
- Cache diagnostics
- Sync status
- Host health
- Pack management
- Retrieval metrics
- System status
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/debug", tags=["Debug & Monitoring"])


def create_debug_routes(
    cache_manager,
    sync_engine,
    failover_orchestrator,
    monitoring_service,
    active_registry,
    retrieval_optimizer
):
    """Create debug API routes"""
    
    @router.get("/packs", tags=["Packs"])
    async def debug_packs():
        """Get cache diagnostics for packs"""
        try:
            packs = cache_manager.list_cached_packs()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cached_packs": packs,
                "total_packs": len(packs),
                "total_size_mb": cache_manager.get_cache_stats()["total_size_mb"]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/cache", tags=["Cache"])
    async def debug_cache():
        """Get cache diagnostics"""
        try:
            stats = cache_manager.get_cache_stats()
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cache_stats": stats,
                "diagnostics": monitoring_service.get_cache_diagnostics()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/retrieval", tags=["Retrieval"])
    async def debug_retrieval():
        """Get retrieval performance diagnostics"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "diagnostics": monitoring_service.get_retrieval_diagnostics(),
                "cache_stats": retrieval_optimizer.get_retrieval_stats()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/host-status", tags=["Failover"])
    async def debug_host_status():
        """Get host connectivity status"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "host_health": failover_orchestrator.health_monitor.get_status(),
                "offline_mode": failover_orchestrator.failover_controller.get_offline_status(),
                "system_status": failover_orchestrator.get_system_status()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/sync", tags=["Sync"])
    async def debug_sync():
        """Get sync engine status"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "last_sync": sync_engine.last_sync_time.isoformat() if sync_engine.last_sync_time else None,
                "active_downloads": {
                    pack_id: sync_engine.get_download_status(pack_id)
                    for pack_id in sync_engine.active_downloads.keys()
                }
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/system", tags=["System"])
    async def debug_system():
        """Get complete system status"""
        try:
            return monitoring_service.get_full_status()
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/active-packs", tags=["Packs"])
    async def debug_active_packs():
        """Get active pack registry"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "active_packs_summary": active_registry.get_active_packs_summary()
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/metrics", tags=["Metrics"])
    async def get_metrics(hours: int = 24):
        """Get time-series metrics"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "metrics": monitoring_service.metrics.get_metrics_summary(),
                "time_series": monitoring_service.metrics.get_time_series_metrics(hours)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/events", tags=["Logging"])
    async def get_recent_events(limit: int = 100, event_type: Optional[str] = None):
        """Get recent debug events"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "events": monitoring_service.event_logger.get_recent_events(limit, event_type)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/errors", tags=["Logging"])
    async def get_error_events(hours: int = 24):
        """Get error events"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "errors": monitoring_service.event_logger.get_error_events(hours)
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    return router
