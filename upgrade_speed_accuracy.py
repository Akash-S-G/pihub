import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        
        # Upgrade Quantization to Q8_0 for better accuracy
        if "\"content_model_file\": \"Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf\"" in src:
            new_src = src.replace(
                "\"content_model_file\": \"Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf\"",
                "\"content_model_file\": \"Meta-Llama-3.1-8B-Instruct-Q8_0.gguf\""
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")
            
        # Enable Flash Attention and Batch size for better speed
        if "CONTENT_LLM = Llama.from_pretrained(" in src:
            new_src = src.replace(
                "        n_threads=int(CONFIG[\"n_threads\"]),",
                "        n_threads=int(CONFIG[\"n_threads\"]),\n        flash_attn=True,  # MASSIVE speedup for long context\n        n_batch=2048,  # Evaluates large chunks of the chapter simultaneously\n        tensor_split=None,  # Auto-split across BOTH Kaggle T4 GPUs"
            )
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Speed and Accuracy Upgrades applied!")
