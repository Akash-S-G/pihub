import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        
        # Add GPU logging right after Llama initialization
        if "CONTENT_LLM = Llama.from_pretrained(" in src:
            new_src = src.replace(
                "        verbose=False\n    )",
                "        verbose=False\n    )\n    import llama_cpp\n    sys_info = llama_cpp.llama_print_system_info().decode('utf-8')\n    logger.info(f\"Llama System Info: {sys_info}\")\n    if 'CUDA = 1' in sys_info or 'BLAS = 1' in sys_info:\n        logger.info(\"✅ GPU ACCELERATION IS ACTIVE AND CONFIRMED!\")\n    else:\n        logger.warning(\"⚠️ GPU IS NOT ACTIVE! Falling back to CPU.\")"
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")
            
        # Change token logging frequency
        if "if tokens % 250 == 0:" in src:
            new_src = src.replace(
                "if tokens % 250 == 0:",
                "if tokens % 50 == 0:"
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("GPU checking logs and finer token streaming added!")
