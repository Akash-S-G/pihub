import json
import ast

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "ARTIFACT_SPECS: Dict[str, Dict[str, Any]] = {" in "".join(cell["source"]):
        lines = "".join(cell["source"]).split("\n")
        in_dict = False
        for i in range(len(lines)):
            line = lines[i]
            if "ARTIFACT_SPECS" in line:
                in_dict = True
            elif in_dict and line.strip() == "}":
                in_dict = False
            elif in_dict and line.strip().startswith('"'):
                # Force strictly 4 space characters
                lines[i] = "    " + line.strip()
        
        new_src = "\n".join(lines)
        try:
            ast.parse(new_src)
            print("Syntax is valid now!")
            cell["source"] = [l + "\n" for l in new_src.split("\n")]
            cell["source"][-1] = cell["source"][-1].rstrip("\n")
        except Exception as e:
            print(f"Still broken: {e}")
        break

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

