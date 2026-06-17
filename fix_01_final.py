import json

with open('/home/akash/Desktop/PIHUB/01_DOCLING_EXTRACTION.ipynb', 'r') as f:
    nb = json.load(f)

new_try_block = [
    "            try:\n",
    "                pil_image = None\n",
    "                if hasattr(pic, 'get_image'):\n",
    "                    image_ref = pic.get_image(doc_obj)\n",
    "                    if hasattr(image_ref, 'pil_image'):\n",
    "                        pil_image = image_ref.pil_image\n",
    "                elif hasattr(pic, 'image') and hasattr(pic.image, 'pil_image'):\n",
    "                    pil_image = pic.image.pil_image\n",
    "                if pil_image:\n",
    "                    img_path = img_dir / f\"{fig_id}.png\"\n",
    "                    pil_image.save(img_path, \"PNG\")\n",
    "                    saved_images[fig_id] = str(img_path)\n",
    "            except Exception as e:\n",
    "                print(f\"Warning: Failed to save image {fig_id}: {e}\")\n"
]

for cell in nb['cells']:
    if cell['cell_type'] == 'code':
        source = cell['source']
        for i, line in enumerate(source):
            if "            try:" in line and "                image = None" in source[i+1]:
                # Found the try block. Let's find the end of it (up to the next empty line or print statement)
                end_idx = i
                for j in range(i, len(source)):
                    if "print(f\"Warning: Failed to save image" in source[j]:
                        end_idx = j
                        break
                
                # We need to replace lines i to end_idx with our new block
                # Since the array will change size, let's just slice it.
                source[i:end_idx+1] = new_try_block
                
                # Cleanup the empty strings we left last time if they exist
                # Look for blank strings in the next few lines
                k = i + len(new_try_block)
                while k < len(source) and source[k] == "":
                    del source[k]
                
                break

with open('/home/akash/Desktop/PIHUB/01_DOCLING_EXTRACTION.ipynb', 'w') as f:
    json.dump(nb, f, indent=2)
