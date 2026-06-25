import os
import re
import shutil

target_dir = "/home/akash/Desktop/PIHUB/TEXTBOOKS"

for root, dirs, files in os.walk(target_dir):
    for file in files:
        if file.endswith(".pdf"):
            basename = file[:-4]
            # Remove "Chapter X " or "Chapter X-" or "Chapter X - "
            new_name = re.sub(r'^chapter\s*\d+\s*[-—]*\s*', '', basename, flags=re.IGNORECASE)
            
            # Replace spaces and special characters with underscore, lowercase
            new_name = re.sub(r'[^a-zA-Z0-9]+', '_', new_name).strip('_').lower()
            
            new_filename = new_name + ".pdf"
            
            old_path = os.path.join(root, file)
            new_path = os.path.join(root, new_filename)
            
            if old_path != new_path:
                print(f"Renaming: '{file}' -> '{new_filename}'")
                os.rename(old_path, new_path)
