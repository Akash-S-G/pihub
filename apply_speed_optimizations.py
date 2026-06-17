import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "CONFIG =" in "".join(cell["source"]):
        src = "".join(cell["source"])
        
        # Disable the 10 non-essential artifacts
        artifacts_to_disable = [
            '"generate_misconceptions": True',
            '"generate_mcq_quiz": True',
            '"generate_short_answer": True',
            '"generate_concept_relationships": True',
            '"generate_image_captions": True',
            '"generate_investigations": True',
            '"generate_teacher_notes": True',
            '"generate_prerequisites": True',
            '"generate_difficulty_analysis": True',
            '"generate_exam_questions": True'
        ]
        
        for art in artifacts_to_disable:
            src = src.replace(art, art.replace("True", "False"))
            
        # Switch model back to Q4_K_M for higher throughput on T4 GPUs
        if '"content_model_file": "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf"' in src:
            src = src.replace(
                '"content_model_file": "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf"',
                '"content_model_file": "Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"'
            )
            
        # Increase n_threads to 8
        if '"n_threads": 4' in src:
            src = src.replace('"n_threads": 4', '"n_threads": 8')
            
        cell["source"] = [l + "\n" for l in src.split("\n")]
        cell["source"][-1] = cell["source"][-1].rstrip("\n")

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Speed Optimizations successfully applied to Notebook 02!")
