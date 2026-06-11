"""
Monitoring and Observability Module

Tracks:
- Pack download metrics
- Cache hit/miss statistics
- Retrieval latency
- Sync status and timing
- Host connectivity
- System resource usage
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, Optional, List
from dataclasses import dataclass, field
import threading
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class MetricsSnapshot:
    """Single metrics snapshot"""
    timestamp: datetime
    cache_hits: int = 0
    cache_misses: int = 0
    pack_downloads: int = 0
    total_downloaded_mb: float = 0.0
    retrieval_queries: int = 0
    avg_retrieval_latency_ms: float = 0.0
    sync_cycles: int = 0
    avg_sync_latency_ms: float = 0.0
    host_uptime_percent: float = 100.0
    cache_utilization_percent: float = 0.0


class MetricsCollector:
    """Collect and aggregate metrics"""
    
    def __init__(self, cache_manager, retention_hours: int = 24):
        """
        Initialize metrics collector
        
        Args:
            cache_manager: PiCacheManager instance
            retention_hours: How long to retain metrics
        """
        self.cache_manager = cache_manager
        self.retention_hours = retention_hours
        
        self.cache_hits = 0
        self.cache_misses = 0
        self.pack_downloads = 0
        self.total_downloaded_mb = 0.0
        self.retrieval_queries = 0
        self.retrieval_latencies: deque = deque(maxlen=1000)
        self.sync_cycles = 0
        self.sync_latencies: deque = deque(maxlen=100)
        
        self.snapshots: deque = deque(maxlen=1440)  # 1 minute * 24 hours
        
        self.lock = threading.RLock()
        logger.info("Metrics collector initialized")
    
    def record_cache_hit(self):
        """Record cache hit"""
        with self.lock:
            self.cache_hits += 1
    
    def record_cache_miss(self):
        """Record cache miss"""
        with self.lock:
            self.cache_misses += 1
    
    def record_pack_download(self, size_mb: float):
        """Record pack download"""
        with self.lock:
            self.pack_downloads += 1
            self.total_downloaded_mb += size_mb
    
    def record_retrieval_query(self, latency_ms: float):
        """Record retrieval query with latency"""
        with self.lock:
            self.retrieval_queries += 1
            self.retrieval_latencies.append(latency_ms)
    
    def record_sync_cycle(self, latency_ms: float):
        """Record sync cycle with latency"""
        with self.lock:
            self.sync_cycles += 1
            self.sync_latencies.append(latency_ms)
    
    def take_snapshot(self) -> MetricsSnapshot:
        """Take a metrics snapshot"""
        with self.lock:
            cache_stats = self.cache_manager.get_cache_stats()
            
            avg_retrieval_latency = (
                sum(self.retrieval_latencies) / len(self.retrieval_latencies)
                if self.retrieval_latencies else 0.0
            )
            
            avg_sync_latency = (
                sum(self.sync_latencies) / len(self.sync_latencies)
                if self.sync_latencies else 0.0
            )
            
            snapshot = MetricsSnapshot(
                timestamp=datetime.utcnow(),
                cache_hits=self.cache_hits,
                cache_misses=self.cache_misses,
                pack_downloads=self.pack_downloads,
                total_downloaded_mb=self.total_downloaded_mb,
                retrieval_queries=self.retrieval_queries,
                avg_retrieval_latency_ms=avg_retrieval_latency,
                sync_cycles=self.sync_cycles,
                avg_sync_latency_ms=avg_sync_latency,
                cache_utilization_percent=cache_stats["utilization_percent"]
            )
            
            self.snapshots.append(snapshot)
            return snapshot
    
    def get_latest_snapshot(self) -> Optional[MetricsSnapshot]:
        """Get latest metrics snapshot"""
        with self.lock:
            return self.snapshots[-1] if self.snapshots else None
    
    def get_metrics_summary(self) -> dict:
        """Get comprehensive metrics summary"""
        with self.lock:
            cache_stats = self.cache_manager.get_cache_stats()
            hit_rate = (
                (self.cache_hits / (self.cache_hits + self.cache_misses)) * 100
                if (self.cache_hits + self.cache_misses) > 0 else 0.0
            )
            
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "cache": {
                    "total_hits": self.cache_hits,
                    "total_misses": self.cache_misses,
                    "hit_rate_percent": hit_rate,
                    "total_entries": cache_stats["total_entries"],
                    "total_size_mb": cache_stats["total_size_mb"],
                    "max_size_mb": cache_stats["max_size_mb"],
                    "utilization_percent": cache_stats["utilization_percent"],
                    "by_category": cache_stats["categories"]
                },
                "packs": {
                    "total_downloads": self.pack_downloads,
                    "total_downloaded_mb": self.total_downloaded_mb
                },
                "retrieval": {
                    "total_queries": self.retrieval_queries,
                    "avg_latency_ms": (
                        sum(self.retrieval_latencies) / len(self.retrieval_latencies)
                        if self.retrieval_latencies else 0.0
                    ),
                    "min_latency_ms": min(self.retrieval_latencies) if self.retrieval_latencies else 0.0,
                    "max_latency_ms": max(self.retrieval_latencies) if self.retrieval_latencies else 0.0
                },
                "sync": {
                    "total_cycles": self.sync_cycles,
                    "avg_latency_ms": (
                        sum(self.sync_latencies) / len(self.sync_latencies)
                        if self.sync_latencies else 0.0
                    )
                }
            }
    
    def get_time_series_metrics(self, hours: int = 24) -> List[dict]:
        """Get time series metrics over period"""
        with self.lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            return [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "cache_hits": s.cache_hits,
                    "cache_misses": s.cache_misses,
                    "retrieval_latency_ms": s.avg_retrieval_latency_ms,
                    "cache_utilization_percent": s.cache_utilization_percent
                }
                for s in self.snapshots
                if s.timestamp >= cutoff_time
            ]


class DebugEventLogger:
    """Log debug events for troubleshooting"""
    
    def __init__(self, max_events: int = 10000):
        self.max_events = max_events
        self.events: deque = deque(maxlen=max_events)
        self.lock = threading.RLock()
    
    def log_event(
        self,
        event_type: str,
        message: str,
        details: Optional[Dict] = None,
        severity: str = "info"
    ):
        """Log a debug event"""
        with self.lock:
            event = {
                "timestamp": datetime.utcnow().isoformat(),
                "type": event_type,
                "message": message,
                "severity": severity,
                "details": details or {}
            }
            self.events.append(event)
            
            level = getattr(logging, severity.upper(), logging.INFO)
            logger.log(level, f"[{event_type}] {message}")
    
    def get_recent_events(self, limit: int = 100, event_type: Optional[str] = None) -> List[dict]:
        """Get recent events"""
        with self.lock:
            events = list(self.events)
            
            if event_type:
                events = [e for e in events if e["type"] == event_type]
            
            return events[-limit:]
    
    def get_error_events(self, hours: int = 24) -> List[dict]:
        """Get error events from last N hours"""
        with self.lock:
            cutoff_time = datetime.utcnow() - timedelta(hours=hours)
            
            return [
                e for e in self.events
                if e["severity"] in ("error", "warning")
                and datetime.fromisoformat(e["timestamp"]) >= cutoff_time
            ]


class MonitoringService:
    """Central monitoring service"""
    
    def __init__(self, cache_manager, health_monitor, failover_controller):
        """Initialize monitoring service"""
        self.cache_manager = cache_manager
        self.health_monitor = health_monitor
        self.failover_controller = failover_controller
        
        self.metrics = MetricsCollector(cache_manager)
        self.event_logger = DebugEventLogger()
        
        logger.info("Monitoring service initialized")
    
    def get_full_status(self) -> dict:
        """Get complete system status"""
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "system": {
                "host_health": self.health_monitor.get_status(),
                "offline_mode": self.failover_controller.get_offline_status()
            },
            "metrics": self.metrics.get_metrics_summary(),
            "recent_errors": self.event_logger.get_error_events(hours=1)
        }
    
    def get_cache_diagnostics(self) -> dict:
        """Get detailed cache diagnostics"""
        stats = self.cache_manager.get_cache_stats()
        cached_packs = self.cache_manager.list_cached_packs()
        
        return {
            "cache_stats": stats,
            "cached_packs": cached_packs,
            "recent_events": self.event_logger.get_recent_events(100)
        }
    
    def get_retrieval_diagnostics(self) -> dict:
        """Get retrieval performance diagnostics"""
        latest_snapshot = self.metrics.get_latest_snapshot()
        
        return {
            "retrieval_metrics": {
                "total_queries": self.metrics.retrieval_queries,
                "avg_latency_ms": self.metrics.get_metrics_summary()["retrieval"].get("avg_latency_ms", 0)
            },
            "cache_hit_rate": (
                (self.metrics.cache_hits / (self.metrics.cache_hits + self.metrics.cache_misses)) * 100
                if (self.metrics.cache_hits + self.metrics.cache_misses) > 0 else 0.0
            ),
            "time_series": self.metrics.get_time_series_metrics(hours=6)
        }
