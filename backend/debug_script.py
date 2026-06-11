import asyncio
from app.pack_generator import PackGenerator
import logging
import json
from qdrant_client import models
from shared.text_normalization import normalize_curriculum_name

logging.basicConfig(level=logging.WARNING)

async def main():
    generator = PackGenerator(
        qdrant_url="http://qdrant:6333",
        qdrant_collection="educational_chunks",
        pack_storage_path="/shared/packs",
        curriculum_graph_path="/shared/work/curriculum_graph.json"
    )
    generator.debug_pack_query()

asyncio.run(main())
