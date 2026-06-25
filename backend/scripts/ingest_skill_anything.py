import yaml
import json
import tarfile
import hashlib
from pathlib import Path
from datetime import datetime, timezone

def dict_hash(d):
    j = json.dumps(d, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{hashlib.sha256(j).hexdigest()}"

source_dir = Path("/home/akash/Desktop/PIHUB/generated_pack_new")
packs_dir = Path("/home/akash/Desktop/PIHUB/shared/packs")
index_path = packs_dir / "pack_index.json"

with open(index_path, "r") as f:
    pack_index = json.load(f)

for pack_path in source_dir.iterdir():
    if not pack_path.is_dir():
        continue
    
    pack_yaml = pack_path / "pack.yaml"
    if not pack_yaml.exists():
        continue
        
    print(f"Processing {pack_path.name}...")
    with open(pack_yaml, "r") as f:
        sa_data = yaml.safe_load(f)
        
    # Map Skill-Anything output to PIHUB artifacts
    artifacts = {
        "summary": sa_data.get("summary", {}),
        "concepts": sa_data.get("concepts", []),
        "glossary": sa_data.get("glossary", []),
        "flashcards": sa_data.get("flashcards", []),
        "quizzes": sa_data.get("quizzes", []),
        "exercises": sa_data.get("exercises", []),
        "takeaways": sa_data.get("takeaways", [])
    }
    
    # We need to find the existing pack for this chapter in PIHUB
    # To do this safely, we search the index
    # We assume pack_path.name matches the chapter roughly, e.g. "electricity"
    target_pack = None
    for p in pack_index:
        if pack_path.name.lower() in p["chapter"].lower():
            target_pack = p
            break
            
    if not target_pack:
        print(f"Could not find matching pack in PIHUB index for {pack_path.name}")
        continue
        
    target_dir = Path(target_pack["pack_dir"])
    
    # Write artifacts to the PIHUB pack directory
    for key, val in artifacts.items():
        with open(target_dir / f"{key}.json", "w") as f:
            json.dump(val, f, indent=2)
            
    # Update manifest
    manifest_file = target_dir / "manifest.json"
    with open(manifest_file, "r") as f:
        manifest = json.load(f)
        
    manifest["artifacts"] = {k: len(v) if isinstance(v, list) else 1 for k, v in artifacts.items() if v}
    manifest["version"] = "2.0.0"
    manifest["generation_metadata"]["source"] = "skill_anything"
    
    checksum_source = {k: v for k, v in manifest.items() if k != "checksum"}
    manifest["checksum"] = dict_hash(checksum_source)
    
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        
    # Update archive
    archive_path = Path(target_pack["archive_path"])
    if archive_path.exists():
        archive_path.unlink()
        
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(target_dir, arcname=".")
        
    # Update index
    target_pack["checksum"] = manifest["checksum"]
    target_pack["artifact_counts"] = manifest["artifacts"]
    target_pack["version"] = "2.0.0"
    
with open(index_path, "w") as f:
    json.dump(pack_index, f, indent=2, sort_keys=True)

print("Ingestion complete!")
