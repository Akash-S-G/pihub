import json

with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if "# 8. FULL NARRATION" in src:
            # We want to replace the entire block that reads STRUCTURED_ROOT
            old_block = """# 8. FULL NARRATION
full_text = ""
for p in STRUCTURED_ROOT.rglob("structured_chapter.json"):
    try:
        j = json.loads(p.read_text("utf-8"))
        for sec in j.get("sections", []):
            full_text += sec.get("content", "") + ". "
    except: pass
if full_text.strip():
    p = synthesize_wav(chunk_text(full_text, 30), VOICE_ROOT / "full_chapter.wav", "full_narration")
    if p: manifest["full_narration"] = p"""

            new_block = """# 8. DETAILED EXPLANATION (Replacing Full Narration)
full_text = ""
for s in read_json("detailed_explanation.json"):
    txt = s.get("payload", {}).get("explanation", "")
    if txt:
        full_text += txt + " "
if full_text.strip():
    p = synthesize_wav(chunk_text(full_text, 30), VOICE_ROOT / "detailed_explanation.wav", "full_narration")
    if p: manifest["full_narration"] = p"""
            
            if old_block in src:
                new_src = src.replace(old_block, new_block)
                cell["source"] = [l + "\n" for l in new_src.split("\n")]
                cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Voice notebook decoupled from Notebook 01!")
