from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="distributed-educational-ai-ecosystem", alias="APP_NAME")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    gateway_host: str = Field(default="0.0.0.0", alias="GATEWAY_HOST")
    gateway_port: int = Field(default=8000, alias="GATEWAY_PORT")

    content_pipeline_url: str = Field(default="http://content-pipeline:8001", alias="CONTENT_PIPELINE_URL")
    inference_service_url: str = Field(default="http://inference-service:8010", alias="INFERENCE_SERVICE_URL")
    pihub_url: str = Field(default="http://pihub:8020", alias="PIHUB_URL")
    experiment_service_url: str = Field(default="http://experiment-service:8040", alias="EXPERIMENT_SERVICE_URL")
    experiment_service_required: bool = Field(default=False, alias="EXPERIMENT_SERVICE_REQUIRED")
    voice_service_url: str = Field(default="http://voice-service:8050", alias="VOICE_SERVICE_URL")
    voice_service_required: bool = Field(default=False, alias="VOICE_SERVICE_REQUIRED")
    qdrant_url: str = Field(default="http://qdrant:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="educational_chunks", alias="QDRANT_COLLECTION")

    embedding_model_name: str = Field(default="BAAI/bge-small-en-v1.5", alias="EMBEDDING_MODEL_NAME")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")

    upload_dir: str = Field(default="/shared/uploads", alias="UPLOAD_DIR")
    work_dir: str = Field(default="/shared/work", alias="WORK_DIR")
    content_dir: str = Field(default="/shared/content", alias="CONTENT_DIR")
    curriculum_graph_path: str = Field(default="/shared/work/curriculum_graph.json", alias="CURRICULUM_GRAPH_PATH")
    curriculum_relation_graph_path: str = Field(default="/shared/work/curriculum_relation_graph.json", alias="CURRICULUM_RELATION_GRAPH_PATH")
    enable_auto_ingestion: bool = Field(default=False, alias="ENABLE_AUTO_INGESTION")
    enable_semantic_educational_chunking: bool = Field(default=True, alias="ENABLE_SEMANTIC_EDUCATIONAL_CHUNKING")
    enable_curriculum_graph_engine: bool = Field(default=True, alias="ENABLE_CURRICULUM_GRAPH_ENGINE")
    enable_educational_retrieval_engine: bool = Field(default=True, alias="ENABLE_EDUCATIONAL_RETRIEVAL_ENGINE")
    
    # Pack Management
    pack_storage_path: str = Field(default="/shared/packs", alias="PACK_STORAGE_PATH")
    pack_service_url: str = Field(default="http://pack-service:8030", alias="PACK_SERVICE_URL")
    
    # Pi Cache Settings
    cache_path: str = Field(default="/cache", alias="CACHE_PATH")
    pi_cache_max_mb: int = Field(default=500, alias="PI_CACHE_MAX_MB")
    pi_cache_db_path: str = Field(default="/cache/cache_index.db", alias="PI_CACHE_DB_PATH")
    
    # Sync Engine Settings
    sync_interval_minutes: int = Field(default=60, alias="SYNC_INTERVAL_MINUTES")
    host_url: str = Field(default="http://192.168.1.100", alias="HOST_URL")
    
    # Failover Settings
    heartbeat_interval_seconds: int = Field(default=30, alias="HEARTBEAT_INTERVAL_SECONDS")
    heartbeat_failure_threshold: int = Field(default=3, alias="HEARTBEAT_FAILURE_THRESHOLD")
    
    # Classroom Settings
    classroom_name: str = Field(default="Classroom A", alias="CLASSROOM_NAME")
    classroom_id: str = Field(default="class_001", alias="CLASSROOM_ID")
    
    # Curriculum Builder Settings
    textbooks_root: str = Field(default="/home/akash/Desktop/PIHUB/TEXTBOOKS", alias="TEXTBOOKS_ROOT")
    curriculum_build_dir: str = Field(default="/shared/curriculum", alias="CURRICULUM_BUILD_DIR")
    curriculum_manifest_path: str = Field(default="/shared/curriculum/curriculum_manifest.json", alias="CURRICULUM_MANIFEST_PATH")
    pack_registry_path: str = Field(default="/shared/curriculum/pack_registry.json", alias="PACK_REGISTRY_PATH")
    enrichment_registry_path: str = Field(default="/shared/curriculum/enrichment_registry.json", alias="ENRICHMENT_REGISTRY_PATH")
    curriculum_version: str = Field(default="1.0.0", alias="CURRICULUM_VERSION")
    max_concurrent_compilation_tasks: int = Field(default=2, alias="MAX_CONCURRENT_COMPILATION_TASKS")
    enable_gemma_content_generation: bool = Field(default=True, alias="ENABLE_GEMMA_CONTENT_GENERATION")
    content_generation_timeout_seconds: float = Field(default=20.0, alias="CONTENT_GENERATION_TIMEOUT_SECONDS")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
