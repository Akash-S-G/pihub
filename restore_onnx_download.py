import json
with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        
        # 1. Remove from CONFIG
        if 'CONFIG = {' in src and '"snac_decoder_dataset":' in src:
            new_source = []
            for line in cell["source"]:
                if '"snac_decoder_dataset":' not in line:
                    new_source.append(line)
            cell["source"] = new_source

        # 2. Update the SNAC_DECODER path logic
        if 'SNAC_DECODER = Path(CONFIG.get("snac_decoder_dataset", ".")) / "decoder_model.onnx"' in src:
            new_source = []
            for line in cell["source"]:
                if 'print("Locating SNAC ONNX Decoder from dataset...")' in line:
                    new_source.append('print("Downloading SNAC ONNX Decoder...")\n')
                elif 'SNAC_DECODER = Path(CONFIG.get("snac_decoder_dataset", "."))' in line:
                    new_source.append('SNAC_DECODER = hf_hub_download(repo_id="onnx-community/snac_24khz-ONNX", filename="onnx/decoder_model.onnx")\n')
                elif 'if not SNAC_DECODER.exists():' in line:
                    continue  # skip the local check since hf_hub_download handles missing files
                else:
                    new_source.append(line)
            cell["source"] = new_source

with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("ONNX Download Restored")
