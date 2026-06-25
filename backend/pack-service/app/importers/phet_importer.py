import json
import logging
from pathlib import Path
from typing import Any

from app.pack_storage.pack_repository import PackRepository

logger = logging.getLogger(__name__)

class PhetImporter:
    def __init__(self, pack_repository: PackRepository):
        self.pack_repository = pack_repository

    async def import_simulations(self, source_dir: Path) -> dict[str, Any]:
        """Import the PHET simulations folder into an official PiHub pack."""
        if not source_dir.exists() or not source_dir.is_dir():
            raise ValueError(f"Source directory {source_dir} does not exist.")
            
        catalog_path = source_dir / "catalog.json"
        if not catalog_path.exists():
            raise ValueError(f"catalog.json not found in {source_dir}")
            
        catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
        simulation_count = len(catalog_data)

        pack_id = "phet_simulations_v1"

        pack_data = {
            "pack_id": pack_id,
            "version": "1.0.0",
            "grade": 0,
            "subject": "mixed",
            "chapter": "phet_simulations",
            "language": "english",
            "artifacts": {
                "static_dir": str(source_dir)
            },
            "artifact_counts": {
                "simulations": simulation_count
            },
            "generation_metadata": {"source": "phet_downloads"},
            "quality_scores": {}
        }

        logger.info(f"Saving PHET simulations pack: {pack_id}")
        record = self.pack_repository.save_pack(pack_data)

        return record
