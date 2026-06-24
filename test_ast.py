import json, ast

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb') as f: nb = json.load(f)
specs_src = ''
for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'ARTIFACT_SPECS: Dict' in ''.join(cell['source']):
        specs_src = ''.join(cell['source'])
        break

tree = ast.parse(specs_src)
for node in tree.body:
    if isinstance(node, ast.AnnAssign) and getattr(node.target, 'id', '') == 'ARTIFACT_SPECS':
        print(f"Found AnnAssign for {node.target.id}")
        keys = [k.value for k in node.value.keys]
        print(keys)
