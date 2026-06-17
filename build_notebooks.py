import json

# ========================
# UPDATE NOTEBOOK 02
# ========================
with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'r') as f:
    nb02 = json.load(f)

for cell in nb02["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if 'CONFIG = {' in src and '"output_root":' in src:
            new_source = []
            for line in cell["source"]:
                new_source.append(line)
                if '"output_root":' in line:
                    new_source.append('    "docling_input_dataset": "/kaggle/input/docling-extraction-output/idp_curriculum_generation",\n')
            cell["source"] = new_source
            
        if 'OUTPUT_ROOT = Path(CONFIG["output_root"])' in src:
            new_source = [
                "OUTPUT_ROOT = Path(CONFIG[\"output_root\"])\n",
                "DOCLING_ROOT = Path(CONFIG.get(\"docling_input_dataset\", CONFIG[\"output_root\"]))\n",
                "\n",
                "CACHE_ROOT = OUTPUT_ROOT / \"cache\"\n",
                "STRUCTURED_ROOT = DOCLING_ROOT / \"structured_chapters\"\n",
                "PACK_ROOT = OUTPUT_ROOT / \"generated_pack\"\n",
                "\n",
                "for path in [CACHE_ROOT, PACK_ROOT]:\n",
                "    path.mkdir(parents=True, exist_ok=True)\n",
                "\n",
                "print(\"Artifact Generator Ready.\")\n",
                "print(f\"Reading structured PDFs from: {STRUCTURED_ROOT}\")\n",
                "print(f\"Writing artifacts to: {PACK_ROOT}\")\n"
            ]
            cell["source"] = new_source

with open('/home/akash/Desktop/PIHUB/02_ARTIFACT_GENERATION.ipynb', 'w') as f:
    json.dump(nb02, f, indent=2)

# ========================
# UPDATE NOTEBOOK 03
# ========================
with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'r') as f:
    nb03 = json.load(f)

for cell in nb03["cells"]:
    if cell["cell_type"] == "code":
        src = "".join(cell["source"])
        if 'OUTPUT_ROOT = Path("/kaggle/working/idp_curriculum_generation")' in src:
            new_source = [
                "import json, os, time, re\n",
                "from pathlib import Path\n",
                "import numpy as np\n",
                "import onnxruntime as ort\n",
                "import soundfile as sf\n",
                "from llama_cpp import Llama\n",
                "\n",
                "CONFIG = {\n",
                "    \"docling_input_dataset\": \"/kaggle/input/docling-extraction-output/idp_curriculum_generation\",\n",
                "    \"artifact_input_dataset\": \"/kaggle/input/artifact-generation-output/idp_curriculum_generation\",\n",
                "    \"output_root\": \"/kaggle/working/idp_curriculum_generation\"\n",
                "}\n",
                "\n",
                "OUTPUT_ROOT = Path(CONFIG[\"output_root\"])\n",
                "DOCLING_ROOT = Path(CONFIG.get(\"docling_input_dataset\", CONFIG[\"output_root\"]))\n",
                "ARTIFACT_ROOT = Path(CONFIG.get(\"artifact_input_dataset\", CONFIG[\"output_root\"]))\n",
                "\n",
                "PACK_ROOT = ARTIFACT_ROOT / \"generated_pack\"\n",
                "STRUCTURED_ROOT = DOCLING_ROOT / \"structured_chapters\"\n",
                "\n",
                "VOICE_ROOT = OUTPUT_ROOT / \"generated_pack_with_voice\" / \"voice\"\n",
                "for d in [\"section_summaries\", \"concepts\", \"glossary\", \"faqs\", \"doubts\", \"flashcards\"]:\n",
                "    (VOICE_ROOT / d).mkdir(parents=True, exist_ok=True)\n",
                "\n",
                "print(f\"Reading structured PDFs from: {STRUCTURED_ROOT}\")\n",
                "print(f\"Reading artifacts from: {PACK_ROOT}\")\n",
                "print(f\"Writing voice outputs to: {VOICE_ROOT}\")\n",
                "\n",
                "SAMPLE_RATE = 24000\n",
                "PAUSE_SAMPLES = int(1.5 * SAMPLE_RATE)\n",
                "\n"
            ]
            # preserve everything from "def snac_codes" downwards
            idx = src.find("def snac_codes")
            rest = src[idx:]
            # The rest needs to be split by \n to preserve lines correctly for json.dump
            new_source.extend([l + "\n" for l in rest.split("\n")])
            # strip the last \n from the last line
            if new_source[-1].endswith("\n\n"):
                 new_source[-1] = new_source[-1][:-1]
            if new_source[-1] == "\n":
                new_source.pop()
            
            cell["source"] = new_source

        # Update zip logic! PACK_ROOT is now read-only, so we zip from PACK_ROOT but save relative to it
        if 'zip_path = OUTPUT_ROOT / "generated_pack_with_voice.zip"' in src:
            new_source = [
                "import zipfile\n",
                "OUTPUT_ZIP_DIR = OUTPUT_ROOT / \"generated_pack_with_voice\"\n",
                "OUTPUT_ZIP_DIR.mkdir(parents=True, exist_ok=True)\n",
                "zip_path = OUTPUT_ROOT / \"generated_pack_with_voice.zip\"\n",
                "\n",
                "with zipfile.ZipFile(zip_path, \"w\", zipfile.ZIP_DEFLATED) as archive:\n",
                "    # Add all JSON artifacts from the read-only Input PACK_ROOT into the zip under 'generated_pack/'\n",
                "    for file_path in PACK_ROOT.rglob(\"*.json\"):\n",
                "        archive.write(file_path, arcname=f\"generated_pack/{file_path.relative_to(PACK_ROOT)}\")\n",
                "\n",
                "    # Add all Voice artifacts into the zip under 'generated_pack/voice/'\n",
                "    for file_path in VOICE_ROOT.rglob(\"*.wav\"):\n",
                "        archive.write(file_path, arcname=f\"generated_pack/voice/{file_path.relative_to(VOICE_ROOT)}\")\n",
                "    \n",
                "    voice_manifest = VOICE_ROOT / \"voice_manifest.json\"\n",
                "    if voice_manifest.exists():\n",
                "        archive.write(voice_manifest, arcname=\"generated_pack/voice/voice_manifest.json\")\n",
                "        \n",
                "    voice_report = VOICE_ROOT / \"voice_generation_report.json\"\n",
                "    if voice_report.exists():\n",
                "        archive.write(voice_report, arcname=\"generated_pack/voice/voice_generation_report.json\")\n",
                "\n",
                "print(\"Process complete. Final zip saved to\", zip_path)\n"
            ]
            cell["source"] = new_source


with open('/home/akash/Desktop/PIHUB/03_VOICE_GENERATION.ipynb', 'w') as f:
    json.dump(nb03, f, indent=2)

print("Notebooks decoupled successfully.")
