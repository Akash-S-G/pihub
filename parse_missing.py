import collections

missing = collections.defaultdict(lambda: collections.defaultdict(list))
with open("missing_chapters.txt", "r") as f:
    for line in f:
        # Missing: grade=grade_6 subject=mathematics slug=playing_with_numbers pdf=TEXTBOOKS/...
        if line.startswith("Missing:"):
            parts = line.strip().split(" ")
            grade = parts[1].split("=")[1].replace("grade_", "Grade ")
            subject = parts[2].split("=")[1].capitalize()
            slug = parts[3].split("=")[1].replace("_", " ").title()
            missing[grade][subject].append(slug)

with open("missing_summary.md", "w") as out:
    out.write("# Missing Chapters (Textbooks vs Artifacts)\n\n")
    out.write("Here are the chapters that exist as PDFs in the `TEXTBOOKS` folder but do **not** have corresponding generated artifacts in the `textbook_artifacts` directory:\n\n")
    for grade in sorted(missing.keys()):
        out.write(f"## {grade}\n")
        for subject in sorted(missing[grade].keys()):
            out.write(f"### {subject}\n")
            for chapter in missing[grade][subject]:
                out.write(f"- {chapter}\n")
            out.write("\n")
