"""
Retrieval Optimization Module

Optimizes:
- Retrieval result caching
- Semantic cache key matching
- Cache-aware routing
- Response streaming
- Latency reduction
"""

import hashlib
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)


class SemanticCacheKey:
    """Generate semantic cache keys for retrieval queries"""
    
    @staticmethod
    def generate(query: str, metadata: Optional[Dict] = None) -> str:
        """
        Generate semantic cache key for a query
        
        Normalizes query and metadata to produce consistent keys
        for semantically similar queries
        """
        # Normalize query
        normalized_query = query.lower().strip()
        
        # Create base key from query
        query_hash = hashlib.sha256(normalized_query.encode()).hexdigest()[:16]
        
        # Add metadata signature if present
        if metadata:
            meta_str = json.dumps(metadata, sort_keys=True)
            meta_hash = hashlib.sha256(meta_str.encode()).hexdigest()[:8]
            key = f"retrieval:{query_hash}:{meta_hash}"
        else:
            key = f"retrieval:{query_hash}"
        
        return key
    
    @staticmethod
    def get_similar_keys(cache_index: Dict, query_key: str, similarity_threshold: float = 0.8) -> List[str]:
        """
        Find similar cached queries
        
        Args:
            cache_index: Cache index dictionary
            query_key: Query key to match
            similarity_threshold: Minimum similarity (0-1)
        
        Returns:
            List of similar cache keys
        """
        similar_keys = []
        query_prefix = query_key.split(":")[1] if ":" in query_key else query_key
        
        for cached_key in cache_index.keys():
            if not cached_key.startswith("retrieval:"):
                continue
            
            cached_prefix = cached_key.split(":")[1] if ":" in cached_key else cached_key
            
            # Simple string similarity (can be enhanced with edit distance)
            if cached_prefix.startswith(query_prefix[:4]):
                similar_keys.append(cached_key)
        
        return similar_keys


class RetrievalCacheManager:
    """Manage retrieval result caching with semantic matching"""
    
    def __init__(
        self,
        cache_manager,
        ttl_hours: int = 24,
        max_results_cached: int = 1000
    ):
        """Initialize retrieval cache manager"""
        self.cache_manager = cache_manager
        self.ttl_seconds = ttl_hours * 3600
        self.max_cached = max_results_cached
        
        self.cache_stats = {
            "hits": 0,
            "misses": 0,
            "semantic_hits": 0
        }
        
        self.lock = threading.RLock()
    
    def cache_retrieval_results(
        self,
        query: str,
        results: List[Dict],
        metadata: Optional[Dict] = None,
        retrieval_latency_ms: float = 0.0
    ) -> bool:
        """
        Cache retrieval results
        
        Args:
            query: Search query
            results: Retrieval results
            metadata: Query metadata (grade, subject, etc.)
            retrieval_latency_ms: Time taken to retrieve
        
        Returns:
            True if cached successfully
        """
        try:
            cache_key = SemanticCacheKey.generate(query, metadata)
            
            cache_value = {
                "query": query,
                "metadata": metadata,
                "results": results,
                "latency_ms": retrieval_latency_ms,
                "cached_at": datetime.utcnow().isoformat(),
                "hit_count": 0
            }
            
            return self.cache_manager.set(
                key=cache_key,
                value=cache_value,
                category="retrieval",
                ttl_seconds=self.ttl_seconds
            )
        
        except Exception as e:
            logger.error(f"Error caching retrieval results: {e}")
            return False
    
    def get_cached_retrieval(
        self,
        query: str,
        metadata: Optional[Dict] = None
    ) -> Optional[List[Dict]]:
        """
        Retrieve cached results for query
        
        Args:
            query: Search query
            metadata: Query metadata
        
        Returns:
            Cached results or None
        """
        with self.lock:
            try:
                cache_key = SemanticCacheKey.generate(query, metadata)
                cached = self.cache_manager.get(cache_key)
                
                if cached:
                    self.cache_stats["hits"] += 1
                    return cached.get("results", [])
                else:
                    self.cache_stats["misses"] += 1
                    return None
            
            except Exception as e:
                logger.error(f"Error retrieving from cache: {e}")
                self.cache_stats["misses"] += 1
                return None
    
    def get_cache_stats(self) -> Dict:
        """Get cache statistics"""
        with self.lock:
            total = self.cache_stats["hits"] + self.cache_stats["misses"]
            hit_rate = (
                (self.cache_stats["hits"] / total * 100)
                if total > 0 else 0
            )
            
            return {
                "total_hits": self.cache_stats["hits"],
                "total_misses": self.cache_stats["misses"],
                "hit_rate_percent": hit_rate,
                "semantic_hits": self.cache_stats["semantic_hits"]
            }


class CacheAwareRetrieval:
    """Retrieval coordinator with caching awareness"""
    
    def __init__(
        self,
        cache_manager,
        retrieval_service_url: str,
        offline_controller=None
    ):
        """
        Initialize cache-aware retrieval
        
        Args:
            cache_manager: PiCacheManager instance
            retrieval_service_url: URL of retrieval service
            offline_controller: Optional offline failover controller
        """
        self.cache_manager = cache_manager
        self.retrieval_url = retrieval_service_url
        self.offline_controller = offline_controller
        
        self.cache_mgr = RetrievalCacheManager(cache_manager)
        self.lock = threading.RLock()
    
    async def search_with_caching(
        self,
        query: str,
        metadata: Optional[Dict] = None,
        use_cache: bool = True,
        force_refresh: bool = False,
        active_pack_registry = None
    ) -> Tuple[List[Dict], bool, float]:
        """
        Search with caching optimization
        
        Args:
            query: Search query
            metadata: Query metadata
            use_cache: Use cache if available
            force_refresh: Bypass cache
            active_pack_registry: Optional pack registry for local search
        
        Returns:
            (results, is_cached, latency_ms)
        """
        start_time = time.time()
        is_cached = False
        results = []
        
        try:
            # Check cache first
            if use_cache and not force_refresh:
                cached_results = self.cache_mgr.get_cached_retrieval(query, metadata)
                if cached_results:
                    is_cached = True
                    results = cached_results
                    latency_ms = (time.time() - start_time) * 1000
                    logger.info(f"Cache hit for query: {query} ({latency_ms:.1f}ms)")
                    return results, is_cached, latency_ms
            
            # Try local active pack search
            if active_pack_registry:
                local_results = active_pack_registry.search_active_packs(
                    query,
                    limit=10
                )
                if local_results:
                    results = local_results
                    latency_ms = (time.time() - start_time) * 1000
                    
                    # Cache results
                    self.cache_mgr.cache_retrieval_results(
                        query, results, metadata, latency_ms
                    )
                    
                    logger.info(f"Local pack search found {len(results)} results ({latency_ms:.1f}ms)")
                    return results, False, latency_ms
            
            # Fall back to remote retrieval if available
            if self.retrieval_url:
                results = await self._remote_retrieval(query, metadata)
                
                latency_ms = (time.time() - start_time) * 1000
                
                # Cache results
                self.cache_mgr.cache_retrieval_results(
                    query, results, metadata, latency_ms
                )
                
                logger.info(f"Remote retrieval found {len(results)} results ({latency_ms:.1f}ms)")
                return results, False, latency_ms
            
            # Offline fallback
            if self.offline_controller:
                cached_results = await self.offline_controller.serve_cached_retrieval(
                    query, metadata
                )
                if cached_results:
                    latency_ms = (time.time() - start_time) * 1000
                    return cached_results, True, latency_ms
            
            latency_ms = (time.time() - start_time) * 1000
            return [], False, latency_ms
        
        except Exception as e:
            logger.error(f"Search error: {e}")
            latency_ms = (time.time() - start_time) * 1000
            
            # Try offline fallback on error
            if self.offline_controller:
                try:
                    cached = await self.offline_controller.serve_cached_retrieval(
                        query, metadata
                    )
                    if cached:
                        return cached, True, latency_ms
                except:
                    pass
            
            return [], False, latency_ms
    
    async def _remote_retrieval(
        self,
        query: str,
        metadata: Optional[Dict] = None
    ) -> List[Dict]:
        """Perform remote retrieval"""
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{self.retrieval_url}/rag/search",
                    json={
                        "query": query,
                        "limit": 10,
                        "metadata": metadata or {}
                    }
                )
                response.raise_for_status()
                
                data = response.json()
                return data.get("results", [])
        
        except Exception as e:
            logger.error(f"Remote retrieval error: {e}")
            return []
    
    def get_retrieval_stats(self) -> Dict:
        """Get retrieval statistics"""
        return self.cache_mgr.get_cache_stats()


class ResponseStreaming:
    """Handle response streaming for large result sets"""
    
    @staticmethod
    def stream_results(results: List[Dict], chunk_size: int = 100):
        """
        Stream results in chunks
        
        Args:
            results: Full result set
            chunk_size: Size of each chunk
        
        Yields:
            Result chunks
        """
        for i in range(0, len(results), chunk_size):
            chunk = results[i:i + chunk_size]
            yield {
                "chunk_index": i // chunk_size,
                "chunk_size": len(chunk),
                "total": len(results),
                "results": chunk
            }
    
    @staticmethod
    async def stream_remote_results(url: str, query: str, chunk_size: int = 100):
        """Stream results from remote endpoint"""
        try:
            import httpx
            
            async with httpx.AsyncClient(timeout=60) as client:
                async with client.stream(
                    "POST",
                    f"{url}/rag/search",
                    json={"query": query, "limit": 1000},
                    timeout=60
                ) as response:
                    response.raise_for_status()
                    
                    buffer = b""
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        buffer += chunk
                        
                        # Try to extract complete JSON objects
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            if line:
                                try:
                                    yield json.loads(line)
                                except json.JSONDecodeError:
                                    pass

                    if buffer.strip():
                        try:
                            yield json.loads(buffer)
                        except json.JSONDecodeError:
                            pass

        except Exception as e:
            logger.error(f"Stream error: {e}")
