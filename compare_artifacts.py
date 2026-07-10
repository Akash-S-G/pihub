import os
from pathlib import Path
import re

textbooks_dir = Path("TEXTBOOKS")
artifacts_dir = Path("textbook_artifacts")

for pdf in textbooks_dir.rglob("*.pdf"):
    # pdf.parent is something like TEXTBOOKS/science/class 10
    # or TEXTBOOKS/mathematics/class 6
    subject = pdf.parent.parent.name
    class_folder = pdf.parent.name
    
    match = re.search(r'class (\d+)', class_folder)
    if not match:
        continue
    
    grade = f"grade_{match.group(1)}"
    
    slug = pdf.stem.replace(" ", "_").replace("-", "_").lower()
    
    artifact_path = artifacts_dir / grade / subject / slug
    if not artifact_path.exists():
        print(f"Missing: grade={grade} subject={subject} slug={slug} pdf={pdf}")

