import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "logging.FileHandler" in "".join(cell["source"]):
        src = "".join(cell["source"])
        
        # Remove the mkdir loop from the bottom
        src = src.replace("for path in [CACHE_ROOT, PACK_ROOT]:\n    path.mkdir(parents=True, exist_ok=True)", "")
        
        # Add it right before the Logging configuration
        src = src.replace(
            "# Logging Configuration", 
            "for path in [OUTPUT_ROOT, CACHE_ROOT, PACK_ROOT]:\n    path.mkdir(parents=True, exist_ok=True)\n\n# Logging Configuration"
        )
        
        cell["source"] = [l + "\n" for l in src.split("\n")]
        cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Logger directory fix applied!")
