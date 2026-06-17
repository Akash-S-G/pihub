import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if "CONTENT_LLM = Llama.from_pretrained(" in src:
            if "llama_print_system_info" not in src:
                # Let's replace print("Model loaded successfully!") with our robust logging
                new_src = src.replace(
                    "    print(\"Model loaded successfully!\")",
                    "    print(\"Model loaded successfully!\")\n    import llama_cpp\n    sys_info = llama_cpp.llama_print_system_info().decode('utf-8')\n    logger.info(f\"Llama System Info: {sys_info}\")\n    if 'CUDA = 1' in sys_info or 'BLAS = 1' in sys_info:\n        logger.info(\"✅ GPU ACCELERATION IS ACTIVE AND CONFIRMED!\")\n    else:\n        logger.warning(\"⚠️ GPU IS NOT ACTIVE! Falling back to CPU.\")"
                )
                cell["source"] = [l + "\n" for l in new_src.split("\n")]
                cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("GPU logs truly added this time!")
