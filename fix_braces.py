import json
import re

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'ARTIFACT_SPECS: Dict' in ''.join(cell['source']):
        src_lines = cell['source']
        for i, line in enumerate(src_lines):
            # Check line 2: "concepts"
            if '"concepts":' in line and line.count('}') < 8:
                # Need to add a closing brace. Let's just blindly add '}' before ',\n'
                src_lines[i] = line.replace('},\n', '}},\n')
            # Check line 14: "teacher_notes"
            if '"teacher_notes":' in line and line.count('}') > 6:
                # Remove an extra closing brace
                src_lines[i] = line.replace('}}},\n', '}},\n')
            # Check line 18: "common_doubts"
            if '"common_doubts":' in line and line.count('}') < 8:
                src_lines[i] = line.replace('},\n', '}},\n')
        
        cell['source'] = src_lines
        break

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)
print("Saved fixed notebook.")
