import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "!pip -q install llama-cpp-python" in "".join(cell["source"]):
        src = "".join(cell["source"])
        # Replace the simple pip install with the CUDA-enabled pip install
        new_src = src.replace(
            "!pip -q install llama-cpp-python jsonschema pandas tqdm huggingface_hub",
            "!CMAKE_ARGS=\"-DGGML_CUDA=on\" pip install -q llama-cpp-python --upgrade --force-reinstall --no-cache-dir\n!pip -q install jsonschema pandas tqdm huggingface_hub"
        )
        cell["source"] = [l + "\n" for l in new_src.split("\n")]
        cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("GPU Installation script updated!")
