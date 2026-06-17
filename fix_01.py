import json
with open('/home/akash/Desktop/PIHUB/01_DOCLING_EXTRACTION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and '"resume": True' in "".join(cell['source']):
        cell['source'] = [line.replace('"resume": True,', '"resume": False,') for line in cell['source']]

with open('/home/akash/Desktop/PIHUB/01_DOCLING_EXTRACTION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)
