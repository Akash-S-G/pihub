import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "Logging Configuration" in "".join(cell["source"]):
        src = "".join(cell["source"])
        
        recovery_code = """
import shutil
import glob

# ==========================================
# AUTO-RESUME & CACHE RECOVERY SCRIPT
# ==========================================
# This automatically scans /kaggle/input/ for any previously generated cache files
# (whether you uploaded them as a Dataset or mounted a previous notebook output)
# and copies them to your active working directory so generation can resume instantly.

recovered_count = 0
for input_path in Path("/kaggle/input").rglob("*.json"):
    if "cache" in input_path.parts and len(input_path.name) == 69: # 64-char sha256 + .json
        dest = CACHE_ROOT / input_path.name
        if not dest.exists():
            shutil.copy2(input_path, dest)
            recovered_count += 1

print(f"Auto-Resume: Successfully recovered {recovered_count} previously generated artifact files into active cache!")
# ==========================================
"""
        
        # Insert it right after the path.mkdir loop
        src = src.replace(
            "for path in [OUTPUT_ROOT, CACHE_ROOT, PACK_ROOT]:\n    path.mkdir(parents=True, exist_ok=True)",
            f"for path in [OUTPUT_ROOT, CACHE_ROOT, PACK_ROOT]:\n    path.mkdir(parents=True, exist_ok=True)\n{recovery_code}"
        )
        
        cell["source"] = [l + "\n" for l in src.split("\n")]
        cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Auto-resume script added!")
