import json

with open("/home/akash/Desktop/PIHUB/specs.json", "r") as f:
    specs = json.load(f)

lines = ["ARTIFACT_SPECS: Dict[str, Dict[str, Any]] = {"]
for i, (k, v) in enumerate(specs.items()):
    spec_str = json.dumps(v, ensure_ascii=False)
    # Fix the lambdas since they were strings
    for l_str in [
        '"lambda n: max(1, 20//n)"',
        '"lambda n: max(1, 8//n)"',
        '"lambda n: max(1, 35//n)"',
        '"lambda n: 1"',
        '"lambda n: max(1, 15//n)"',
        '"lambda n: max(1, 25//n)"',
        '"lambda n: max(1, 30//n)"',
        '"lambda n: max(1, 10//n)"',
        '"lambda n: \\"all\\""'
    ]:
        spec_str = spec_str.replace(l_str, l_str.replace('"', ''))
        
    comma = "," if i < len(specs) - 1 else ""
    lines.append(f"    \"{k}\": {spec_str}{comma}")
lines.append("}")

final_str = "\n".join(lines)

with open("/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb", "r") as f:
    nb = json.load(f)

for cell in nb["cells"]:
    if cell["cell_type"] == "code" and "ARTIFACT_SPECS: Dict[str, Dict[str, Any]] = {" in "".join(cell["source"]):
        cell["source"] = [l + "\n" for l in final_str.split("\n")]
        # strip the last \n from the last line
        if cell["source"][-1].endswith("\n"):
            cell["source"][-1] = cell["source"][-1][:-1]

with open("/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb", "w") as f:
    json.dump(nb, f, indent=2)

print("Successfully injected valid ARTIFACT_SPECS.")
