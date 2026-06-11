"""Parse folder hierarchy to extract curriculum metadata."""

import re
from pathlib import Path
from typing import Optional

from language_detector import LanguageDetector
from subject_mapper import SubjectMapper


class FolderParser:
    """Parse TEXTBOOKS folder hierarchy to extract curriculum structure."""

    @staticmethod
    def extract_grade_from_folder_name(folder_name: str) -> Optional[int]:
        """
        Extract grade from folder name.

        Examples:
            "class 1" -> 1
            "class 8 part 1" -> 8
            "class 10" -> 10

        Args:
            folder_name: Folder name

        Returns:
            Grade number or None
        """
        # Match "class N" or "class N part M"
        match = re.search(r"class\s+(\d+)", folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        # Try standalone digits
        match = re.search(r"^(\d+)(?:\s|$)", folder_name)
        if match:
            return int(match.group(1))

        return None

    @staticmethod
    def extract_part_from_folder_name(folder_name: str) -> Optional[int]:
        """
        Extract part number from folder name.

        Examples:
            "class 7 part 1" -> 1
            "class 8 part 2" -> 2

        Args:
            folder_name: Folder name

        Returns:
            Part number or None
        """
        match = re.search(r"part\s+(\d+)", folder_name, re.IGNORECASE)
        if match:
            return int(match.group(1))

        return None

    @classmethod
    def extract_chapter_from_filename(cls, filename: str) -> str:
        """
        Extract chapter name from PDF filename.

        Examples:
            "Proportional Reasoning – 1.pdf" -> "Proportional Reasoning"
            "A Square and A Cube.pdf" -> "A Square and A Cube"
            "So Many Toys (Data Handling).pdf" -> "So Many Toys"

        Args:
            filename: PDF filename

        Returns:
            Chapter name
        """
        # Remove .pdf extension
        name = filename.replace(".pdf", "").replace(".PDF", "")

        # Remove part indicators like " – 1", " - 1", " (Part 1)"
        name = re.sub(r"\s*[-–]\s*\d+\s*$", "", name)
        name = re.sub(r"\s*\(Part\s+\d+\)\s*$", "", name, flags=re.IGNORECASE)

        # Remove trailing numbers and dashes
        name = re.sub(r"\s*[-–]\s*\d+\s*$", "", name)

        # For files like "10th Kan Maths Part- 1" extract subject part
        # These are usually full textbooks, not individual chapters
        if re.search(r"^\d+(?:st|nd|rd|th)\s+", name, re.IGNORECASE):
            # This is a full textbook, extract the subject
            match = re.search(r"(?:maths|science|social|english|hindi)\s+(?:part|part-)?", name, re.IGNORECASE)
            if match:
                return name[: match.end()].strip()

        return name.strip()

    @classmethod
    def is_textbook_file(cls, filename: str) -> bool:
        """
        Check if filename is a textbook PDF.

        Args:
            filename: Filename to check

        Returns:
            True if it's likely a PDF textbook file
        """
        if not filename.lower().endswith(".pdf"):
            return False

        # Exclude temporary/upload files
        if filename.startswith("media_to_upload"):
            return False

        return True

    @classmethod
    def parse_curriculum_path(cls, file_path: Path, textbooks_root: Path) -> dict:
        """
        Parse a complete curriculum path.

        Args:
            file_path: Path to PDF file
            textbooks_root: Root TEXTBOOKS directory

        Returns:
            Dictionary with parsed curriculum metadata
        """
        relative_path = file_path.relative_to(textbooks_root)
        parts = relative_path.parts

        # Detect language from path
        language = LanguageDetector.detect_from_path(file_path)

        # Extract subject from top-level directory
        subject = None
        subject_dir = Path(parts[0]) if parts else None
        if subject_dir:
            subject = SubjectMapper.extract_subject_from_directory(subject_dir)

        # Extract grade from intermediate directory (usually "class N")
        grade = None
        if len(parts) >= 2:
            folder_name = parts[1]
            grade = cls.extract_grade_from_folder_name(folder_name)
            part = cls.extract_part_from_folder_name(folder_name)
        else:
            part = None

        # Extract chapter from filename
        chapter = cls.extract_chapter_from_filename(file_path.name) if len(parts) > 0 else None

        return {
            "language": language,
            "subject": subject,
            "grade": grade,
            "part": part,
            "chapter": chapter,
            "filename": file_path.name,
            "relative_path": str(relative_path),
            "full_path": str(file_path),
        }
