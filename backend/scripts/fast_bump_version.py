import json
import tarfile
import hashlib
from pathlib import Path

def dict_hash(d):
    j = json.dumps(d, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return f"sha256:{hashlib.sha256(j).hexdigest()}"

packs_dir = Path("/home/akash/Desktop/PIHUB/backend/shared/packs")
for pack_path in packs_dir.iterdir():
    if not pack_path.is_dir() or pack_path.name == "pdf_manifests":
        continue
    manifest_file = pack_path / "manifest.json"
    if not manifest_file.exists():
        continue
    
    with open(manifest_file, "r") as f:
        manifest = json.load(f)
    
    if manifest.get("version") == "2.0.0":
        continue
        
    print(f"Bumping {pack_path.name} to 2.0.0")
    manifest["version"] = "2.0.0"
    
    # Recalculate checksum
    checksum_source = {k: v for k, v in manifest.items() if k != "checksum"}
    manifest["checksum"] = dict_hash(checksum_source)
    
    with open(manifest_file, "w") as f:
        json.dump(manifest, f, indent=2, sort_keys=True)
        
    # Re-tar
    archive_path = packs_dir / f"{pack_path.name}.pack"
    if archive_path.exists():
        archive_path.unlink()
        
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(pack_path, arcname=".")

print("Done bumping versions!")
