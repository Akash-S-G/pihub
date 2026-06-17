import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if "result = CONTENT_LLM(prompt, max_tokens=CONFIG[\"max_tokens\"], temperature=CONFIG[\"temperature\"], top_p=CONFIG[\"top_p\"])" in src:
            new_code = []
            for line in cell["source"]:
                if 'result = CONTENT_LLM(prompt, max_tokens=CONFIG["max_tokens"], temperature=CONFIG["temperature"], top_p=CONFIG["top_p"])' in line:
                    new_code.append('        stream = CONTENT_LLM(prompt, max_tokens=CONFIG["max_tokens"], temperature=CONFIG["temperature"], top_p=CONFIG["top_p"], stream=True)\n')
                    new_code.append('        raw = ""\n')
                    new_code.append('        tokens = 0\n')
                    new_code.append('        for chunk in stream:\n')
                    new_code.append('            token_text = chunk["choices"][0]["text"]\n')
                    new_code.append('            raw += token_text\n')
                    new_code.append('            tokens += 1\n')
                    new_code.append('            if tokens % 250 == 0:\n')
                    new_code.append('                logger.info(f"[{chapter.document_id}] \'{artifact_name}\' - {tokens} tokens generated...")\n')
                elif 'raw = result["choices"][0]["text"]' in line:
                    continue
                elif 'tokens = result["usage"]["completion_tokens"]' in line:
                    continue
                else:
                    new_code.append(line)
            cell["source"] = new_code

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Streaming logs added.")
