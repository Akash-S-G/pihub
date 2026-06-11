"""Language detection from curriculum source paths and metadata."""

import re
from pathlib import Path
from typing import Optional


class LanguageDetector:
    """Detect language from directory names and PDF metadata."""

    # Language directory patterns
    LANGUAGE_PATTERNS = {
        "kannada": [r"kannada", r"kan\s", r"ಕನ್ನಡ"],
        "hindi": [r"hindi", r"hin\s", r"हिन्दी"],
        "marathi": [r"marathi", r"mar\s", r"मराठी"],
        "tamil": [r"tamil", r"tam\s", r"தமிழ்"],
        "telugu": [r"telugu", r"tel\s", r"తెలుగు"],
        "english": [r"english", r"eng\s"],
    }

    DEFAULT_LANGUAGE = "english"

    @classmethod
    def detect_from_path(cls, file_path: Path) -> str:
        """
        Detect language from file path.

        Args:
            file_path: Path to PDF or directory

        Returns:
            Language code (e.g., "english", "kannada")
        """
        path_str = str(file_path).lower()

        for language, patterns in cls.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, path_str, re.IGNORECASE):
                    return language

        return cls.DEFAULT_LANGUAGE

    @classmethod
    def detect_from_filename(cls, filename: str) -> str:
        """
        Detect language from filename.

        Args:
            filename: Filename to analyze

        Returns:
            Language code
        """
        filename_lower = filename.lower()

        for language, patterns in cls.LANGUAGE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, filename_lower, re.IGNORECASE):
                    return language

        return cls.DEFAULT_LANGUAGE

    @classmethod
    def detect_from_pdf_metadata(cls, pdf_path: Path) -> Optional[str]:
        """
        Detect language from PDF metadata (title, subject, author).

        Args:
            pdf_path: Path to PDF file

        Returns:
            Language code or None if detection fails
        """
        try:
            import PyPDF2

            with open(pdf_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                metadata = reader.metadata
                if metadata:
                    # Check title and subject for language hints
                    title = str(metadata.get("/Title", "")).lower()
                    subject = str(metadata.get("/Subject", "")).lower()
                    text = f"{title} {subject}"

                    for language, patterns in cls.LANGUAGE_PATTERNS.items():
                        for pattern in patterns:
                            if re.search(pattern, text, re.IGNORECASE):
                                return language
        except Exception:
            # If PDF reading fails, fall back to path-based detection
            pass

        return None
