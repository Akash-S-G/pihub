import json
with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        
        # 1. Add to CONFIG
        if 'CONFIG = {' in src and '"output_root":' in src:
            new_source = []
            for line in cell["source"]:
                if '"output_root":' in line:
                    new_source.append('    "snac_decoder_dataset": "/kaggle/input/snac-onnx-decoder",\n')
                new_source.append(line)
            cell["source"] = new_source

        # 2. Update the SNAC_DECODER path logic
        if 'SNAC_DECODER = hf_hub_download(' in src:
            new_source = []
            for line in cell["source"]:
                if 'print("Downloading SNAC ONNX Decoder...")' in line:
                    new_source.append('print("Locating SNAC ONNX Decoder from dataset...")\n')
                elif 'SNAC_DECODER = hf_hub_download(repo_id="hubertsiuzdak/snac_24khz-ONNX"' in line:
                    new_source.append('SNAC_DECODER = Path(CONFIG.get("snac_decoder_dataset", ".")) / "decoder_model.onnx"\n')
                    new_source.append('if not SNAC_DECODER.exists(): raise FileNotFoundError(f"Missing ONNX Decoder: {SNAC_DECODER}")\n')
                else:
                    new_source.append(line)
            cell["source"] = new_source

with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("ONNX Loading Fixed")
