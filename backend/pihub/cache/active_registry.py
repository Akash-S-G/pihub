"""
Active Classroom Pack System

Manages:
- Runtime pack activation/deactivation
- Classroom-specific pack sets
- Preloading of active packs
- Memory management
- Pack indexing for fast access
"""

import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import threading

logger = logging.getLogger(__name__)


class ActivePackRegistry:
    """Registry of active packs for classrooms"""
    
    def __init__(
        self,
        cache_manager,
        cache_path: str = "/cache"
    ):
        """
        Initialize active pack registry
        
        Args:
            cache_manager: PiCacheManager instance
            cache_path: Cache directory path
        """
        self.cache_manager = cache_manager
        self.cache_path = Path(cache_path)
        
        self.active_packs: Dict[str, dict] = {}  # pack_id -> pack_data
        self.classroom_assignments: Dict[str, List[str]] = {}  # classroom_id -> [pack_ids]
        self.preloaded_indices: Dict[str, dict] = {}  # pack_id -> search index
        
        self.lock = threading.RLock()
        self.state_file = self.cache_path / "active_registry.json"
        
        self._load_state()
        logger.info("Active pack registry initialized")
    
    def activate_pack(
        self,
        pack_id: str,
        preload: bool = True,
        index_for_search: bool = True
    ) -> bool:
        """
        Activate a pack for runtime use
        
        Args:
            pack_id: Pack identifier
            preload: Preload pack data into memory
            index_for_search: Create search index
        
        Returns:
            True if activation succeeded
        """
        with self.lock:
            try:
                # Get pack from cache
                pack_data = self.cache_manager.get_cached_pack(pack_id)
                if not pack_data:
                    logger.error(f"Pack {pack_id} not found in cache")
                    return False
                
                # Mark as active in cache manager
                self.cache_manager.mark_pack_active(pack_id)
                
                # Store in active registry
                self.active_packs[pack_id] = {
                    "pack_id": pack_id,
                    "manifest": pack_data.get("manifest", {}),
                    "activated_at": datetime.utcnow().isoformat(),
                    "access_count": 0,
                    "preloaded": preload
                }
                
                # Create search index if requested
                if index_for_search:
                    self._build_search_index(pack_id, pack_data)
                
                self._save_state()
                logger.info(f"Pack {pack_id} activated")
                return True
            
            except Exception as e:
                logger.error(f"Error activating pack {pack_id}: {e}")
                return False
    
    def deactivate_pack(self, pack_id: str) -> bool:
        """Deactivate a pack"""
        with self.lock:
            try:
                if pack_id in self.active_packs:
                    del self.active_packs[pack_id]
                
                if pack_id in self.preloaded_indices:
                    del self.preloaded_indices[pack_id]
                
                self.cache_manager.mark_pack_inactive(pack_id)
                self._save_state()
                
                logger.info(f"Pack {pack_id} deactivated")
                return True
            
            except Exception as e:
                logger.error(f"Error deactivating pack {pack_id}: {e}")
                return False
    
    def assign_pack_to_classroom(
        self,
        classroom_id: str,
        pack_ids: List[str]
    ) -> bool:
        """
        Assign packs to a classroom
        
        Args:
            classroom_id: Classroom identifier
            pack_ids: List of pack IDs to assign
        
        Returns:
            True if assignment succeeded
        """
        with self.lock:
            try:
                # Activate all packs for this classroom
                for pack_id in pack_ids:
                    if pack_id not in self.active_packs:
                        if not self.activate_pack(pack_id):
                            logger.warning(f"Failed to activate pack {pack_id}")
                
                self.classroom_assignments[classroom_id] = pack_ids
                self._save_state()
                
                logger.info(f"Assigned {len(pack_ids)} packs to classroom {classroom_id}")
                return True
            
            except Exception as e:
                logger.error(f"Error assigning packs to classroom: {e}")
                return False
    
    def get_classroom_packs(self, classroom_id: str) -> List[Dict]:
        """Get packs assigned to a classroom"""
        with self.lock:
            pack_ids = self.classroom_assignments.get(classroom_id, [])
            
            return [
                self.active_packs[pid]
                for pid in pack_ids
                if pid in self.active_packs
            ]
    
    def search_active_packs(
        self,
        query: str,
        classroom_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """
        Search across active packs
        
        Args:
            query: Search query
            classroom_id: Optional classroom filter
            limit: Max results
        
        Returns:
            List of matching chunks
        """
        with self.lock:
            results = []
            query_lower = query.lower()
            
            # Determine which packs to search
            if classroom_id:
                pack_ids = self.classroom_assignments.get(classroom_id, [])
            else:
                pack_ids = list(self.active_packs.keys())
            
            # Search each active pack
            for pack_id in pack_ids:
                if pack_id not in self.active_packs:
                    continue
                
                pack_data = self.active_packs[pack_id]
                chunks = pack_data.get("manifest", {}).get("chunks", [])
                
                # Simple full-text search
                for chunk in chunks:
                    text = chunk.get("text", "").lower()
                    if query_lower in text:
                        results.append({
                            "pack_id": pack_id,
                            "chunk_id": chunk.get("chunk_id"),
                            "text": chunk.get("text"),
                            "metadata": chunk.get("metadata", {})
                        })
                        
                        if len(results) >= limit:
                            return results
            
            return results
    
    def _build_search_index(self, pack_id: str, pack_data: Dict):
        """Build search index for pack chunks"""
        try:
            chunks = pack_data.get("chunks", [])
            
            # Simple inverted index
            index = {}
            
            for chunk in chunks:
                text = chunk.get("text", "").lower()
                words = text.split()
                
                for word in words:
                    if word not in index:
                        index[word] = []
                    index[word].append({
                        "chunk_id": chunk.get("chunk_id"),
                        "position": text.find(word)
                    })
            
            self.preloaded_indices[pack_id] = index
            logger.info(f"Built search index for {pack_id}")
        
        except Exception as e:
            logger.error(f"Error building search index: {e}")
    
    def get_active_packs_summary(self) -> Dict:
        """Get summary of active packs"""
        with self.lock:
            return {
                "total_active_packs": len(self.active_packs),
                "active_packs": list(self.active_packs.keys()),
                "classrooms": self.classroom_assignments,
                "total_classrooms": len(self.classroom_assignments),
                "indexed_packs": list(self.preloaded_indices.keys())
            }
    
    def record_pack_access(self, pack_id: str):
        """Record access to a pack for statistics"""
        with self.lock:
            if pack_id in self.active_packs:
                self.active_packs[pack_id]["access_count"] += 1
                self.active_packs[pack_id]["last_accessed"] = datetime.utcnow().isoformat()
    
    def cleanup_inactive_packs(self) -> int:
        """
        Remove inactive packs from active registry
        
        Returns:
            Number of packs removed
        """
        with self.lock:
            # Find packs not assigned to any classroom
            assigned_packs = set()
            for pack_ids in self.classroom_assignments.values():
                assigned_packs.update(pack_ids)
            
            to_remove = []
            for pack_id in self.active_packs.keys():
                if pack_id not in assigned_packs:
                    to_remove.append(pack_id)
            
            for pack_id in to_remove:
                self.deactivate_pack(pack_id)
            
            logger.info(f"Cleaned up {len(to_remove)} inactive packs")
            return len(to_remove)
    
    def _save_state(self):
        """Save registry state to disk"""
        try:
            state = {
                "timestamp": datetime.utcnow().isoformat(),
                "active_packs": self.active_packs,
                "classroom_assignments": self.classroom_assignments
            }
            
            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)
        
        except Exception as e:
            logger.error(f"Error saving state: {e}")
    
    def _load_state(self):
        """Load registry state from disk"""
        try:
            if self.state_file.exists():
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                
                self.active_packs = state.get("active_packs", {})
                self.classroom_assignments = state.get("classroom_assignments", {})
                
                logger.info(
                    f"Loaded state: {len(self.active_packs)} active packs, "
                    f"{len(self.classroom_assignments)} classrooms"
                )
        
        except Exception as e:
            logger.error(f"Error loading state: {e}")


class PackPreloader:
    """Preload packs into memory for faster access"""
    
    def __init__(self, registry: ActivePackRegistry, max_preload_mb: int = 100):
        """Initialize preloader"""
        self.registry = registry
        self.max_preload_mb = max_preload_mb
        self.current_preloaded_mb = 0
    
    async def preload_classroom_packs(self, classroom_id: str) -> Tuple[int, int]:
        """
        Preload all packs for a classroom
        
        Args:
            classroom_id: Classroom identifier
        
        Returns:
            (success_count, failure_count)
        """
        packs = self.registry.get_classroom_packs(classroom_id)
        success = 0
        failures = 0
        
        for pack in packs:
            try:
                pack_id = pack.get("pack_id")
                # Preload logic here
                logger.info(f"Preloaded pack {pack_id}")
                success += 1
            except Exception as e:
                logger.error(f"Preload error: {e}")
                failures += 1
        
        return success, failures
