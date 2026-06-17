import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "Auto-Resume: Successfully recovered" in "".join(cell["source"]):
        src = "".join(cell["source"])
        
        # We will replace the auto-resume script with a more verbose one
        old_recovery = """recovered_count = 0
for input_path in Path("/kaggle/input").rglob("*.json"):
    if "cache" in input_path.parts and len(input_path.name) == 69: # 64-char sha256 + .json
        dest = CACHE_ROOT / input_path.name
        if not dest.exists():
            shutil.copy2(input_path, dest)
            recovered_count += 1

print(f"Auto-Resume: Successfully recovered {recovered_count} previously generated artifact files into active cache!")"""

        new_recovery = """print("--- AUTO-RESUME DIAGNOSTICS ---")
print("Scanning /kaggle/input for cache files...")
import os
for root, dirs, files in os.walk("/kaggle/input"):
    for d in dirs:
        if d == "cache":
            print(f"Found cache directory at: {os.path.join(root, d)}")

recovered_count = 0
for input_path in Path("/kaggle/input").rglob("*.json"):
    if "cache" in input_path.parts and len(input_path.name) == 69:
        dest = CACHE_ROOT / input_path.name
        if not dest.exists():
            shutil.copy2(input_path, dest)
            recovered_count += 1
            
print(f"Auto-Resume: Successfully recovered {recovered_count} previously generated artifact files into active cache!")
print("-------------------------------")"""
        
        if old_recovery in src:
            new_src = src.replace(old_recovery, new_recovery)
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Verbose auto-resume script added!")
