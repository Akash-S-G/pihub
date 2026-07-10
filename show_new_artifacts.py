import json
import random
from pathlib import Path

# Load missing chapters from the generated report
# I will just scan textbook_artifacts for files created in the last hour
import time
import os

artifacts_dir = Path("/home/akash/Desktop/PIHUB/textbook_artifacts")
current_time = time.time()
one_hour_ago = current_time - 3600

new_artifacts = {}

for grade_dir in artifacts_dir.glob("grade_*"):
    grade = grade_dir.name
    if grade not in ["grade_6", "grade_7", "grade_8", "grade_9", "grade_10"]:
        continue
    for subject_dir in grade_dir.iterdir():
        if not subject_dir.is_dir():
            continue
        subject = subject_dir.name
        
        for chapter_dir in subject_dir.iterdir():
            summary_file = chapter_dir / "artifacts" / "summary.json"
            if not summary_file.exists():
                continue
                
            mtime = os.path.getmtime(summary_file)
            if mtime > one_hour_ago:
                if grade not in new_artifacts:
                    new_artifacts[grade] = {}
                if subject not in new_artifacts[grade]:
                    new_artifacts[grade][subject] = []
                new_artifacts[grade][subject].append(summary_file)

markdown_out = "# Sample of Newly Generated Artifacts\n\n"

for grade in sorted(new_artifacts.keys()):
    markdown_out += f"## {grade.replace('_', ' ').title()}\n"
    for subject in sorted(new_artifacts[grade].keys()):
        markdown_out += f"### {subject.title()}\n"
        
        # Pick one random newly generated artifact
        sample_file = random.choice(new_artifacts[grade][subject])
        chapter_name = sample_file.parent.parent.name.replace('_', ' ').title()
        
        try:
            with open(sample_file, "r") as f:
                data = json.load(f)
                
            markdown_out += f"**Chapter:** {chapter_name}\n"
            markdown_out += f"**Title:** {data.get('title', 'Unknown')}\n\n"
            markdown_out += f"**Summary:**\n{data.get('summary', 'No summary')}\n\n"
            
            # Show a flashcard too if available
            flashcard_file = sample_file.parent / "flashcards.json"
            if flashcard_file.exists():
                with open(flashcard_file, "r") as f:
                    fc_data = json.load(f)
                if fc_data:
                    fc = fc_data[0]
                    markdown_out += f"**Sample Flashcard:**\n"
                    markdown_out += f"- *Q:* {fc.get('question', '')}\n"
                    markdown_out += f"- *A:* {fc.get('answer', '')}\n\n"
                    
        except Exception as e:
            markdown_out += f"Error reading {sample_file}: {e}\n\n"
            
with open("/home/akash/.gemini/antigravity/brain/eff65094-ec33-4e6e-8d64-ad623cd92c3e/new_artifacts_sample.md", "w") as f:
    f.write(markdown_out)

