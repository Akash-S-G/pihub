import json

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb = json.load(f)

for cell in nb['cells']:
    if cell['cell_type'] == 'code' and 'OUTPUT_ROOT = Path(CONFIG["output_root"])' in "".join(cell['source']) and 'import json' not in "".join(cell['source']):
        new_src = [
            "!pip -q install llama-cpp-python jsonschema pandas tqdm huggingface_hub\n",
            "\n",
            "import json, logging, os, re, time, hashlib, zipfile\n",
            "from dataclasses import dataclass, field\n",
            "from pathlib import Path\n",
            "from typing import Any, Dict, List\n",
            "from tqdm.auto import tqdm\n",
            "from jsonschema import validate as jsonschema_validate\n",
            "\n"
        ] + cell['source']
        cell['source'] = new_src

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)

print("Fixed imports!")
