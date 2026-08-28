from pathlib import Path

import logfire
from unstructured.partition.auto import partition


def parse_office(file_path: str) -> str:
    """
    Parse Office documents such as DOCX and PPTX using Unstructured.

    Unstructured automatically detects the document type
    and extracts its textual content.
    """
    with logfire.span(
        "Office Document Parsing",
        filename=file_path,
    ):
        try:
            path = Path(file_path)

            if not path.exists():
                raise FileNotFoundError(
                    f"Office file not found: {file_path}"
                )

            if path.suffix.lower() not in {".docx", ".pptx"}:
                raise ValueError(
                    f"Unsupported Office format: {path.suffix}"
                )

            elements = partition(filename=str(path))

            full_text = "\n".join(
                str(element).strip()
                for element in elements
                if str(element).strip()
            )

            if not full_text:
                logfire.warning(
                    "Unstructured returned empty text",
                    filename=file_path,
                )
            else:
                logfire.info(
                    "Office document parsed successfully",
                    filename=file_path,
                    characters=len(full_text),
                    elements=len(elements),
                )

            return full_text

        except Exception as e:
            logfire.error(
                "Office document parsing failed",
                filename=file_path,
                error=str(e),
            )
            raise