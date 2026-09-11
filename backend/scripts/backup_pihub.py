#!/usr/bin/env python3
"""
PIHUB Comprehensive Data Backup & Export Utility
Exports:
  1. Qdrant Vector DB Snapshot (Vector embeddings + collection schema)
  2. Textbook PDFs & Raw Source Library
  3. Compiled Educational Packs & Artifacts (quizzes, flashcards, glossaries, summaries)
  4. Curriculum Graphs (curriculum_graph.json, curriculum_relation_graph.json)
  5. Offline Media & PhET Simulations Store
  6. Database files (SQLite / Cache DBs)
Creates a single compressed tarball archive: pihub_full_backup_<timestamp>.tar.gz
"""

from __future__ import annotations

import datetime
import json
import os
import shutil
import sys
import urllib.request
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
LOCAL_RUN_DIR = ROOT_DIR / ".local_run"
TEXTBOOKS_DIR = ROOT_DIR.parent / "TEXTBOOKS"
BACKUP_BASE_DIR = ROOT_DIR / "backups"


def create_qdrant_snapshot(output_dir: Path) -> bool:
    """Trigger Qdrant API to create and download a snapshot of educational_chunks."""
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    collection = os.getenv("QDRANT_COLLECTION", "educational_chunks")
    
    print(f"📦 [1/6] Creating Qdrant Snapshot for collection '{collection}'...")
    snapshot_endpoint = f"{qdrant_url}/collections/{collection}/snapshots"
    
    try:
        req = urllib.request.Request(snapshot_endpoint, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            snapshot_name = data.get("result", {}).get("name")
            if not snapshot_name:
                print("   ⚠️  Failed to get snapshot name from response")
                return False
            
            print(f"   ✓ Snapshot created: {snapshot_name}")
            
            # Download snapshot
            download_url = f"{snapshot_endpoint}/{snapshot_name}"
            target_file = output_dir / snapshot_name
            print(f"   Downloading snapshot from {download_url}...")
            urllib.request.urlretrieve(download_url, target_file)
            print(f"   ✓ Qdrant snapshot saved to {target_file.name} ({target_file.stat().st_size / 1024 / 1024:.2f} MB)")
            return True
    except Exception as exc:
        print(f"   ⚠️  Could not export Qdrant snapshot automatically ({exc})")
        print("   (Ensure Qdrant is running on port 6333 or export manually via /collections/{name}/snapshots)")
        return False


def copy_directory_safe(src: Path, dst: Path, desc: str) -> None:
    if not src.exists():
        print(f"   ⚠️  Source path {src} not found (skipping {desc})")
        return
    print(f"   Copying {desc} from {src}...")
    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.log", "*.tmp", "__pycache__", ".venv"))
    print(f"   ✓ {desc} backed up.")


def copy_file_safe(src: Path, dst: Path, desc: str) -> None:
    if not src.exists():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    print(f"   ✓ Backed up file {src.name} -> {desc}")


def main() -> None:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    target_backup_dir = BACKUP_BASE_DIR / f"pihub_backup_{timestamp}"
    target_backup_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print(f"🚀 STARTING PIHUB BACKUP EXPORT -> {target_backup_dir.name}")
    print("=" * 60)

    # 1. Qdrant Snapshot
    qdrant_dir = target_backup_dir / "qdrant_vector_db"
    qdrant_dir.mkdir(exist_ok=True)
    create_qdrant_snapshot(qdrant_dir)

    # 2. Textbook PDFs & Raw Library
    print("\n📚 [2/6] Backing up Textbook PDFs...")
    copy_directory_safe(TEXTBOOKS_DIR, target_backup_dir / "textbooks", "Textbook PDFs")

    # 3. Compiled Educational Packs & Artifacts
    print("\n🎒 [3/6] Backing up Educational Packs & Artifacts...")
    copy_directory_safe(LOCAL_RUN_DIR / "packs", target_backup_dir / "packs", "Educational Packs")
    copy_directory_safe(LOCAL_RUN_DIR / "curriculum", target_backup_dir / "curriculum", "Curriculum Packs")

    # 4. Curriculum Graphs
    print("\n🕸️  [4/6] Backing up Curriculum Graphs & Work Files...")
    work_dst = target_backup_dir / "work"
    copy_directory_safe(LOCAL_RUN_DIR / "work", work_dst, "Curriculum Work Files")

    # 5. Media & Simulations
    print("\n📹 [5/6] Backing up Offline Media & PhET Simulations...")
    copy_directory_safe(LOCAL_RUN_DIR / "media", target_backup_dir / "media", "Offline Media & Simulations")

    # 6. Database Files
    print("\n🗄️  [6/6] Backing up Databases & Index Caches...")
    for db_path in ROOT_DIR.glob("**/*.sqlite3"):
        if ".local_run" not in str(db_path) and "venv" not in str(db_path):
            copy_file_safe(db_path, target_backup_dir / "databases" / db_path.name, "Database file")
    
    cache_db = LOCAL_RUN_DIR / "cache" / "cache_index.db"
    if cache_db.exists():
        copy_file_safe(cache_db, target_backup_dir / "databases" / "cache_index.db", "Cache Index DB")

    # Create archive
    print("\n📦 Compressing full backup into .tar.gz archive...")
    archive_path = BACKUP_BASE_DIR / f"pihub_full_backup_{timestamp}.tar.gz"
    shutil.make_archive(str(archive_path).replace(".tar.gz", ""), "gztar", target_backup_dir)
    
    print("=" * 60)
    print("✅ BACKUP COMPLETED SUCCESSFULLY!")
    print(f"📁 Backup Directory: {target_backup_dir}")
    print(f"🎁 Compressed Archive: {archive_path} ({archive_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print("=" * 60)


if __name__ == "__main__":
    main()
