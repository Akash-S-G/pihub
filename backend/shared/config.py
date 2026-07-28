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
    gateway_http_timeout_seconds: float = Field(default=900.0, alias="GATEWAY_HTTP_TIMEOUT_SECONDS")
    qdrant_url: str = Field(default="http://qdrant:6333", alias="QDRANT_URL")
    qdrant_collection: str = Field(default="educational_chunks_bge_m3", alias="QDRANT_COLLECTION")

    embedding_model_name: str = Field(default="BAAI/bge-m3", alias="EMBEDDING_MODEL_NAME")
    embedding_device: str = Field(default="cpu", alias="EMBEDDING_DEVICE")
    embedding_cache_dir: str = Field(default="/shared/models/sentence-transformers/embedding", alias="EMBEDDING_CACHE_DIR")
    local_retrieval_model_name: str = Field(default="BAAI/bge-m3", alias="LOCAL_RETRIEVAL_MODEL_NAME")
    local_retrieval_device: str = Field(default="cpu", alias="LOCAL_RETRIEVAL_DEVICE")
    local_retrieval_cache_dir: str = Field(default="/shared/models/sentence-transformers/retrieval", alias="LOCAL_RETRIEVAL_CACHE_DIR")

    upload_dir: str = Field(default="/shared/uploads", alias="UPLOAD_DIR")
    work_dir: str = Field(default="/shared/work", alias="WORK_DIR")
    content_dir: str = Field(default="/shared/content", alias="CONTENT_DIR")
    curriculum_graph_path: str = Field(default="/shared/work/curriculum_graph.json", alias="CURRICULUM_GRAPH_PATH")
    curriculum_relation_graph_path: str = Field(default="/shared/work/curriculum_relation_graph.json", alias="CURRICULUM_RELATION_GRAPH_PATH")
    enable_auto_ingestion: bool = Field(default=False, alias="ENABLE_AUTO_INGESTION")
    enable_ai_artifact_generation: bool = Field(default=True, alias="ENABLE_AI_ARTIFACT_GENERATION")
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

    # Enriched content agent (videos / real-world / simulations)
    enable_web_enrichment: bool = Field(default=True, alias="ENABLE_WEB_ENRICHMENT")
    web_enrichment_timeout_seconds: float = Field(default=8.0, alias="WEB_ENRICHMENT_TIMEOUT_SECONDS")
    web_enrichment_max_per_topic: int = Field(default=4, alias="WEB_ENRICHMENT_MAX_PER_TOPIC")
    youtube_api_key: str = Field(default="", alias="YOUTUBE_API_KEY")
    enrichment_user_agent: str = Field(
        default="Mozilla/5.0 (compatible; PIHUB-EnrichmentBot/1.0)",
        alias="ENRICHMENT_USER_AGENT",
    )
    # Languages to fetch enrichment for (comma-separated). Both are stored so the
    # offline app can serve Kannada and English side by side.
    enrichment_languages: str = Field(default="en,kn", alias="ENRICHMENT_LANGUAGES")

    # Offline media store (downloaded + compressed videos/images)
    enable_media_download: bool = Field(default=True, alias="ENABLE_MEDIA_DOWNLOAD")
    media_storage_path: str = Field(default="/shared/media", alias="MEDIA_STORAGE_PATH")
    media_download_timeout_seconds: float = Field(default=180.0, alias="MEDIA_DOWNLOAD_TIMEOUT_SECONDS")
    media_max_video_height: int = Field(default=480, alias="MEDIA_MAX_VIDEO_HEIGHT")
    media_video_crf: int = Field(default=28, alias="MEDIA_VIDEO_CRF")  # H.264 CRF: visually lossless-ish, small
    media_video_preset: str = Field(default="slow", alias="MEDIA_VIDEO_PRESET")
    media_max_videos_per_topic: int = Field(default=1, alias="MEDIA_MAX_VIDEOS_PER_TOPIC")
    media_max_images_per_topic: int = Field(default=2, alias="MEDIA_MAX_IMAGES_PER_TOPIC")

    # Cobalt API (self-hosted media downloader — replaces yt-dlp)
    cobalt_api_url: str = Field(default="http://cobalt:9000", alias="COBALT_API_URL")

    # MongoDB — stores media + enrichment metadata for offline access
    mongo_url: str = Field(default="mongodb://mongo:27017", alias="MONGO_URL")
    mongo_db: str = Field(default="pihub", alias="MONGO_DB")
    enable_mongo_storage: bool = Field(default=True, alias="ENABLE_MONGO_STORAGE")

    # Qdrant collection for enrichment records (videos/articles/sims/examples)
    enrichment_collection: str = Field(default="enrichment_resources", alias="ENRICHMENT_COLLECTION")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
