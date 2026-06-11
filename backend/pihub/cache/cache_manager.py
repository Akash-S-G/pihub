"""
Pi Lightweight Cache Layer

Implements:
- LRU cache with configurable size limits
- Retrieval result caching
- Pack caching
- Cache persistence across restart
- Fast lookup indexing
"""

import json
import hashlib
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict
import threading

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry"""
    key: str
    value: str  # JSON-serialized value
    category: str  # 'pack', 'retrieval', 'session'
    size_bytes: int
    created_at: float
    last_accessed: float
    access_count: int = 0
    ttl_seconds: Optional[int] = None


class PiCacheManager:
    """LRU cache manager for Pi edge node"""
    
    def __init__(
        self,
        cache_path: str = "/cache",
        max_size_mb: int = 500,
        db_path: Optional[str] = None,
        cleanup_interval_seconds: int = 3600
    ):
        """
        Initialize cache manager
        
        Args:
            cache_path: Root cache directory
            max_size_mb: Maximum cache size in MB
            db_path: SQLite database path for persistence
            cleanup_interval_seconds: Interval for cleanup/eviction tasks
        """
        self.cache_path = Path(cache_path)
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.current_size_bytes = 0
        self.cleanup_interval = cleanup_interval_seconds
        
        # Initialize directories
        self.cache_path.mkdir(parents=True, exist_ok=True)
        (self.cache_path / "active_packs").mkdir(exist_ok=True)
        (self.cache_path / "retrieval").mkdir(exist_ok=True)
        (self.cache_path / "session").mkdir(exist_ok=True)
        (self.cache_path / "sync_temp").mkdir(exist_ok=True)
        
        # Database for metadata
        self.db_path = db_path or str(self.cache_path / "cache_index.db")
        self._init_database()
        
        # In-memory index for fast lookups
        self.index: Dict[str, CacheEntry] = {}
        self.lock = threading.RLock()
        
        # Load index from database
        self._load_index()
        
        # Start cleanup thread
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            daemon=True
        )
        self.cleanup_thread.start()
        logger.info(f"Pi cache initialized: {self.cache_path}, max {max_size_mb}MB")
    
    def _init_database(self):
        """Initialize SQLite database for cache metadata"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cache_entries (
                key TEXT PRIMARY KEY,
                value TEXT,
                category TEXT,
                size_bytes INTEGER,
                created_at REAL,
                last_accessed REAL,
                access_count INTEGER,
                ttl_seconds INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pack_index (
                pack_id TEXT PRIMARY KEY,
                version TEXT,
                location TEXT,
                downloaded_at REAL,
                active INTEGER
            )
        """)
        conn.commit()
        conn.close()
    
    def _load_index(self):
        """Load cache index from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM cache_entries")
            
            for row in cursor:
                entry = CacheEntry(
                    key=row["key"],
                    value=row["value"],
                    category=row["category"],
                    size_bytes=row["size_bytes"],
                    created_at=row["created_at"],
                    last_accessed=row["last_accessed"],
                    access_count=row["access_count"],
                    ttl_seconds=row["ttl_seconds"]
                )
                self.index[entry.key] = entry
                self.current_size_bytes += entry.size_bytes
            
            conn.close()
            logger.info(f"Loaded {len(self.index)} cache entries from database")
        
        except Exception as e:
            logger.error(f"Error loading cache index: {e}")
    
    def get(self, key: str) -> Optional[Any]:
        """
        Retrieve value from cache
        
        Args:
            key: Cache key
        
        Returns:
            Deserialized value or None if not found/expired
        """
        with self.lock:
            entry = self.index.get(key)
            
            if not entry:
                return None
            
            # Check TTL
            if entry.ttl_seconds:
                age = time.time() - entry.created_at
                if age > entry.ttl_seconds:
                    self._delete_entry(entry)
                    return None
            
            # Update access tracking
            entry.last_accessed = time.time()
            entry.access_count += 1
            self._update_entry_db(entry)
            
            try:
                return json.loads(entry.value)
            except json.JSONDecodeError:
                return entry.value
    
    def set(
        self,
        key: str,
        value: Any,
        category: str = "session",
        ttl_seconds: Optional[int] = None
    ) -> bool:
        """
        Store value in cache
        
        Args:
            key: Cache key
            value: Value to store (will be JSON-serialized)
            category: Cache category (pack, retrieval, session)
            ttl_seconds: Time-to-live in seconds
        
        Returns:
            True if stored successfully
        """
        with self.lock:
            # Serialize value
            try:
                if isinstance(value, str):
                    serialized = value
                else:
                    serialized = json.dumps(value)
            except Exception as e:
                logger.error(f"Error serializing value: {e}")
                return False
            
            size_bytes = len(serialized.encode('utf-8'))
            
            # Check if replacement of existing entry
            if key in self.index:
                old_entry = self.index[key]
                self.current_size_bytes -= old_entry.size_bytes
            
            # Evict if necessary
            while self.current_size_bytes + size_bytes > self.max_size_bytes:
                if not self._evict_lru():
                    logger.warning("Cannot evict more entries to make space")
                    return False
            
            # Create new entry
            now = time.time()
            entry = CacheEntry(
                key=key,
                value=serialized,
                category=category,
                size_bytes=size_bytes,
                created_at=now,
                last_accessed=now,
                access_count=0,
                ttl_seconds=ttl_seconds
            )
            
            self.index[key] = entry
            self.current_size_bytes += size_bytes
            self._save_entry_db(entry)
            
            return True
    
    def cache_retrieval_result(
        self,
        query: str,
        results: List[Dict],
        ttl_hours: int = 24
    ) -> bool:
        """
        Cache a retrieval query result
        
        Args:
            query: Search query
            results: Retrieval results
            ttl_hours: Cache TTL in hours
        
        Returns:
            True if cached successfully
        """
        key = f"retrieval:{self._hash_query(query)}"
        ttl_seconds = ttl_hours * 3600
        
        return self.set(
            key=key,
            value=results,
            category="retrieval",
            ttl_seconds=ttl_seconds
        )
    
    def get_cached_retrieval(self, query: str) -> Optional[List[Dict]]:
        """Get cached retrieval results for a query"""
        key = f"retrieval:{self._hash_query(query)}"
        return self.get(key)
    
    def cache_pack(
        self,
        pack_id: str,
        manifest: Dict,
        chunks: List[Dict],
        location: str
    ) -> bool:
        """
        Cache a downloaded pack
        
        Args:
            pack_id: Pack identifier
            manifest: Pack manifest
            chunks: Educational chunks
            location: Path where pack is stored
        
        Returns:
            True if cached successfully
        """
        pack_data = {
            "pack_id": pack_id,
            "manifest": manifest,
            "chunks": chunks,
            "location": location,
            "cached_at": datetime.utcnow().isoformat()
        }
        
        key = f"pack:{pack_id}"
        success = self.set(
            key=key,
            value=pack_data,
            category="pack",
            ttl_seconds=None  # Packs don't expire automatically
        )
        
        # Also update pack index
        if success:
            self._update_pack_index(pack_id, manifest.get("version"), location)
        
        return success
    
    def get_cached_pack(self, pack_id: str) -> Optional[Dict]:
        """Get cached pack data"""
        key = f"pack:{pack_id}"
        return self.get(key)
    
    def mark_pack_active(self, pack_id: str):
        """Mark a pack as actively used in classroom"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE pack_index SET active = 1 WHERE pack_id = ?",
            (pack_id,)
        )
        conn.commit()
        conn.close()
    
    def mark_pack_inactive(self, pack_id: str):
        """Mark a pack as inactive (can be evicted)"""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "UPDATE pack_index SET active = 0 WHERE pack_id = ?",
            (pack_id,)
        )
        conn.commit()
        conn.close()
    
    def list_cached_packs(self) -> List[Dict]:
        """List all cached packs"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT * FROM pack_index")
            
            packs = []
            for row in cursor:
                packs.append({
                    "pack_id": row["pack_id"],
                    "version": row["version"],
                    "location": row["location"],
                    "downloaded_at": row["downloaded_at"],
                    "active": bool(row["active"])
                })
            
            conn.close()
            return packs
        
        except Exception as e:
            logger.error(f"Error listing cached packs: {e}")
            return []
    
    def clear_category(self, category: str) -> int:
        """
        Clear all entries in a category
        
        Args:
            category: Cache category to clear
        
        Returns:
            Number of entries cleared
        """
        with self.lock:
            keys_to_delete = [k for k, v in self.index.items() if v.category == category]
            
            for key in keys_to_delete:
                entry = self.index[key]
                self.current_size_bytes -= entry.size_bytes
                del self.index[key]
                self._delete_entry_db(key)
            
            logger.info(f"Cleared {len(keys_to_delete)} entries from category {category}")
            return len(keys_to_delete)
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            categories = {}
            for entry in self.index.values():
                if entry.category not in categories:
                    categories[entry.category] = {"count": 0, "size_mb": 0}
                categories[entry.category]["count"] += 1
                categories[entry.category]["size_mb"] += entry.size_bytes / (1024 * 1024)
            
            return {
                "total_entries": len(self.index),
                "total_size_mb": self.current_size_bytes / (1024 * 1024),
                "max_size_mb": self.max_size_bytes / (1024 * 1024),
                "utilization_percent": (self.current_size_bytes / self.max_size_bytes) * 100,
                "categories": categories
            }
    
    def _hash_query(self, query: str) -> str:
        """Hash query string for cache key"""
        return hashlib.sha256(query.encode()).hexdigest()[:16]
    
    def _evict_lru(self) -> bool:
        """Evict least-recently-used entry"""
        with self.lock:
            # Find LRU entry (excluding active packs)
            lru_entry = None
            
            for entry in self.index.values():
                # Skip active packs
                if entry.category == "pack":
                    pack_data = json.loads(entry.value)
                    if self._is_pack_active(pack_data.get("pack_id")):
                        continue
                
                if lru_entry is None or entry.last_accessed < lru_entry.last_accessed:
                    lru_entry = entry
            
            if lru_entry:
                logger.info(f"Evicting LRU entry: {lru_entry.key}")
                self._delete_entry(lru_entry)
                return True
            
            return False
    
    def _is_pack_active(self, pack_id: str) -> bool:
        """Check if pack is marked as active"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.execute(
                "SELECT active FROM pack_index WHERE pack_id = ?",
                (pack_id,)
            )
            row = cursor.fetchone()
            conn.close()
            
            return bool(row[0]) if row else False
        except Exception:
            return False
    
    def _delete_entry(self, entry: CacheEntry):
        """Delete entry from cache and database"""
        if entry.key in self.index:
            del self.index[entry.key]
            self.current_size_bytes -= entry.size_bytes
        
        self._delete_entry_db(entry.key)
    
    def _cleanup_worker(self):
        """Background cleanup thread"""
        while True:
            try:
                time.sleep(self.cleanup_interval)
                
                with self.lock:
                    # Remove expired entries
                    expired_keys = []
                    now = time.time()
                    
                    for key, entry in self.index.items():
                        if entry.ttl_seconds and (now - entry.created_at) > entry.ttl_seconds:
                            expired_keys.append(key)
                    
                    for key in expired_keys:
                        entry = self.index[key]
                        self._delete_entry(entry)
                    
                    if expired_keys:
                        logger.info(f"Cleaned up {len(expired_keys)} expired entries")
            
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
    
    def _save_entry_db(self, entry: CacheEntry):
        """Save entry to database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO cache_entries
                (key, value, category, size_bytes, created_at, last_accessed, access_count, ttl_seconds)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.key, entry.value, entry.category, entry.size_bytes,
                entry.created_at, entry.last_accessed, entry.access_count, entry.ttl_seconds
            ))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error saving entry to database: {e}")
    
    def _update_entry_db(self, entry: CacheEntry):
        """Update entry in database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                UPDATE cache_entries
                SET last_accessed = ?, access_count = ?
                WHERE key = ?
            """, (entry.last_accessed, entry.access_count, entry.key))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating entry in database: {e}")
    
    def _delete_entry_db(self, key: str):
        """Delete entry from database"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM cache_entries WHERE key = ?", (key,))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error deleting entry from database: {e}")
    
    def _update_pack_index(self, pack_id: str, version: str, location: str):
        """Update pack in index"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO pack_index
                (pack_id, version, location, downloaded_at, active)
                VALUES (?, ?, ?, ?, ?)
            """, (pack_id, version, location, time.time(), 0))
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Error updating pack index: {e}")
