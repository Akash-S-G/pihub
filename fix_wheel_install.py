import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "llama-cpp-python" in "".join(cell["source"]):
        src = "".join(cell["source"])
        if "!CMAKE_ARGS" in src:
            new_src = src.replace(
                "!CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install -q llama-cpp-python --upgrade --force-reinstall --no-cache-dir",
                "!pip install -q llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121"
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Installation script updated to use pre-compiled wheels!")
