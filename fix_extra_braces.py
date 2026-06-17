import json
import ast
import re

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "ARTIFACT_SPECS: Dict" in "".join(cell["source"]):
        src = "".join(cell["source"])
        lines = src.split('\n')
        
        for i in range(len(lines)):
            if lines[i].strip().startswith('"'):
                # Replace 8 closing braces with 7 closing braces
                lines[i] = re.sub(r'\}\}\}\}\}\}\}\},', r'}}}}}}},', lines[i])
                lines[i] = re.sub(r'\}\}\}\}\}\}\}\}\}', r'}}}}}}}}', lines[i]) # just in case
        
        new_src = '\n'.join(lines)
        
        try:
            ast.parse(new_src)
            print("Syntax is completely valid now!")
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")
        except Exception as e:
            print(f"Still broken: {e}")
        break

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

