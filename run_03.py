import json
with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        lines = []
        for line in cell['source']:
            if not line.strip().startswith('!'):
                lines.append(line)
        src = "".join(lines)
        
        # Modify CONFIG definition so that it works locally
        src = src.replace('"/kaggle/working/idp_curriculum_generation"', '"/home/akash/Desktop/PIHUB/idp_curriculum_generation"')
        src = src.replace('    "docling_input_dataset": "/kaggle/input/docling-extraction-output/idp_curriculum_generation",\n', '')
        src = src.replace('    "artifact_input_dataset": "/kaggle/input/artifact-generation-output/idp_curriculum_generation",\n', '')
        
        exec(src, globals())
