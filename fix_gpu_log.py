import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "Llama System Info:" in "".join(cell["source"]):
        src = "".join(cell["source"])
        if "if 'CUDA = 1' in sys_info or 'BLAS = 1' in sys_info:" in src:
            new_src = src.replace(
                "if 'CUDA = 1' in sys_info or 'BLAS = 1' in sys_info:",
                "if 'CUDA = 1' in sys_info or 'CUDA : ARCHS' in sys_info or 'BLAS = 1' in sys_info:"
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("GPU log fixed!")
