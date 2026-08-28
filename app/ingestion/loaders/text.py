from pathlib import Path

import logfire


def parse_text(file_path: str) -> str:
    """
    Parse a plain text file and return its content.
    """
    with logfire.span("Text Parsing", filename=file_path):
        try:
            path = Path(file_path)

            if not path.exists():
                raise FileNotFoundError(
                    f"Text file not found: {file_path}"
                )

            if path.suffix.lower() != ".txt":
                raise ValueError(
                    f"Expected a .txt file, got: {path.suffix}"
                )

            with path.open(
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as file:
                text = file.read()

            if not text.strip():
                logfire.warning(
                    "Text file is empty",
                    filename=file_path,
                )
            else:
                logfire.info(
                    "Text file parsed successfully",
                    filename=file_path,
                    characters=len(text),
                )

            return text

        except Exception as e:
            logfire.error(
                "Text parsing failed",
                filename=file_path,
                error=str(e),
            )
            raise