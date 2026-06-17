import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "llama-cpp-python" in "".join(cell["source"]):
        src = "".join(cell["source"])
        if "--extra-index-url" in src:
            new_src = src.replace(
                "!pip install -q llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121",
                "!pip install -q https://abetlen.github.io/llama-cpp-python/whl/cu121/llama-cpp-python/llama_cpp_python-0.3.4-cp312-cp312-linux_x86_64.whl --force-reinstall --no-cache-dir"
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Forced direct wheel URL!")
