"""Master curriculum pack registry for distribution and sync."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MasterPackRegistry:
    """Centralized registry of all compiled educational packs."""

    def __init__(self, version: str = "1.0.0"):
        """
        Initialize master pack registry.

        Args:
            version: Registry version
        """
        self.version = version
        self.registry: Dict = {
            "metadata": {
                "version": version,
                "created_at": None,
                "last_updated": None,
                "total_packs": 0,
                "total_size_bytes": 0,
                "registry_hash": None,
            },
            "packs": {},
            "index": {
                "by_grade": {},
                "by_subject": {},
                "by_language": {},
            },
        }

    def register_pack(
        self,
        pack_id: str,
        grade: int,
        subject: str,
        chapter: str,
        language: str = "english",
        version: str = "1.0.0",
        checksum: str = "",
        size_bytes: int = 0,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Register a compiled pack in the master registry.

        Args:
            pack_id: Unique pack identifier
            grade: Grade level
            subject: Subject area
            chapter: Chapter name
            language: Language code
            version: Pack version
            checksum: Content checksum for integrity
            size_bytes: Pack size in bytes
            metadata: Additional metadata
        """
        pack_entry = {
            "pack_id": pack_id,
            "grade": grade,
            "subject": subject,
            "chapter": chapter,
            "language": language,
            "version": version,
            "checksum": checksum,
            "size_bytes": size_bytes,
            "created_at": datetime.utcnow().isoformat(),
            "metadata": metadata or {},
        }

        self.registry["packs"][pack_id] = pack_entry

        # Update indexes
        self._update_indexes(pack_id, grade, subject, language)

    def _update_indexes(self, pack_id: str, grade: int, subject: str, language: str) -> None:
        """
        Update index structures for quick lookup.

        Args:
            pack_id: Pack ID
            grade: Grade level
            subject: Subject area
            language: Language code
        """
        # Index by grade
        if grade not in self.registry["index"]["by_grade"]:
            self.registry["index"]["by_grade"][grade] = []

        self.registry["index"]["by_grade"][grade].append(pack_id)

        # Index by subject
        if subject not in self.registry["index"]["by_subject"]:
            self.registry["index"]["by_subject"][subject] = []

        self.registry["index"]["by_subject"][subject].append(pack_id)

        # Index by language
        if language not in self.registry["index"]["by_language"]:
            self.registry["index"]["by_language"][language] = []

        self.registry["index"]["by_language"][language].append(pack_id)

    def get_packs_for_grade(self, grade: int) -> List[Dict]:
        """
        Get all packs for a specific grade.

        Args:
            grade: Grade level

        Returns:
            List of pack entries
        """
        pack_ids = self.registry["index"]["by_grade"].get(grade, [])
        return [self.registry["packs"][pid] for pid in pack_ids if pid in self.registry["packs"]]

    def get_packs_for_subject(self, subject: str) -> List[Dict]:
        """
        Get all packs for a specific subject.

        Args:
            subject: Subject area

        Returns:
            List of pack entries
        """
        pack_ids = self.registry["index"]["by_subject"].get(subject, [])
        return [self.registry["packs"][pid] for pid in pack_ids if pid in self.registry["packs"]]

    def get_packs_for_language(self, language: str) -> List[Dict]:
        """
        Get all packs for a specific language.

        Args:
            language: Language code

        Returns:
            List of pack entries
        """
        pack_ids = self.registry["index"]["by_language"].get(language, [])
        return [self.registry["packs"][pid] for pid in pack_ids if pid in self.registry["packs"]]

    def get_pack(self, pack_id: str) -> Optional[Dict]:
        """
        Get a specific pack entry.

        Args:
            pack_id: Pack ID

        Returns:
            Pack entry or None
        """
        return self.registry["packs"].get(pack_id)

    def finalize(self) -> Dict:
        """
        Finalize registry with metadata and integrity hash.

        Returns:
            Finalized registry
        """
        self.registry["metadata"]["last_updated"] = datetime.utcnow().isoformat()
        self.registry["metadata"]["total_packs"] = len(self.registry["packs"])

        # Calculate total size
        total_size = sum(pack.get("size_bytes", 0) for pack in self.registry["packs"].values())
        self.registry["metadata"]["total_size_bytes"] = total_size

        # Compute registry hash
        registry_hash = self._compute_hash()
        self.registry["metadata"]["registry_hash"] = registry_hash

        return self.registry

    def _compute_hash(self) -> str:
        """
        Compute SHA256 hash of registry for integrity.

        Returns:
            SHA256 hash
        """
        # Create a copy without the hash to avoid circular dependency
        registry_copy = {k: v for k, v in self.registry.items()}
        if "metadata" in registry_copy and "registry_hash" in registry_copy["metadata"]:
            registry_copy["metadata"] = {k: v for k, v in registry_copy["metadata"].items() if k != "registry_hash"}

        registry_str = json.dumps(registry_copy, sort_keys=False, separators=(",", ":"), default=str)

        return hashlib.sha256(registry_str.encode()).hexdigest()

    def save(self, output_path: Path) -> None:
        """
        Save registry to JSON.

        Args:
            output_path: Path to save registry
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        self.finalize()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.registry, f, indent=2)

        logger.info(f"Master pack registry saved to {output_path}")

    @staticmethod
    def load(path: Path) -> "MasterPackRegistry":
        """
        Load registry from JSON.

        Args:
            path: Path to registry file

        Returns:
            Loaded registry
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        registry = MasterPackRegistry(version=data["metadata"]["version"])
        registry.registry = data

        return registry

    def validate(self) -> bool:
        """
        Validate registry integrity.

        Returns:
            True if valid
        """
        # Verify all packs have required fields
        required_fields = ["pack_id", "grade", "subject", "chapter", "language", "version"]

        for pack_id, pack_entry in self.registry["packs"].items():
            for field in required_fields:
                if field not in pack_entry:
                    logger.error(f"Pack {pack_id} missing required field: {field}")
                    return False

        # Verify indexes are consistent
        for grade, pack_ids in self.registry["index"]["by_grade"].items():
            for pack_id in pack_ids:
                if pack_id not in self.registry["packs"]:
                    logger.error(f"Index references non-existent pack: {pack_id}")
                    return False

        logger.info("Registry validation passed")
        return True

    def print_summary(self) -> None:
        """Print registry summary."""
        meta = self.registry["metadata"]
        print("\n" + "=" * 60)
        print("MASTER PACK REGISTRY SUMMARY")
        print("=" * 60)
        print(f"Version: {meta['version']}")
        print(f"Total Packs: {meta['total_packs']}")
        print(f"Total Size: {meta['total_size_bytes'] / (1024**2):.1f} MB")
        print(f"Last Updated: {meta['last_updated']}")
        print(f"Registry Hash: {meta['registry_hash'][:16]}...")
        print()
        print("Packs by Grade:")
        for grade in sorted(self.registry["index"]["by_grade"].keys()):
            count = len(self.registry["index"]["by_grade"][grade])
            print(f"  Grade {grade}: {count} packs")
        print()
        print("Packs by Subject:")
        for subject in sorted(self.registry["index"]["by_subject"].keys()):
            count = len(self.registry["index"]["by_subject"][subject])
            print(f"  {subject}: {count} packs")
        print()
        print("=" * 60)
