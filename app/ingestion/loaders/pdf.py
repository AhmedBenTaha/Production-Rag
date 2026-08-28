import logfire
from pypdf import PdfReader


def parse_pdf(file_path: str) -> str:
    """
    Extract text from a PDF locally using pypdf.

    Falls back to pdfplumber for pages where pypdf
    fails to extract meaningful text.
    """
    with logfire.span("PDF Parsing (local)", filename=file_path):
        try:
            reader = PdfReader(file_path)
            total_pages = len(reader.pages)

            logfire.info(
                "PDF loaded",
                filename=file_path,
                total_pages=total_pages,
            )

            page_texts: list[str | None] = [None] * total_pages
            blank_pages: list[int] = []

            # Primary extraction using pypdf
            for i, page in enumerate(reader.pages):
                text = page.extract_text() or ""

                if text.strip():
                    page_texts[i] = text
                else:
                    blank_pages.append(i + 1)

            # Fallback extraction using pdfplumber
            if blank_pages:
                logfire.info(
                    "Some pages returned no text from pypdf",
                    blank_pages=blank_pages,
                )

                try:
                    import pdfplumber

                    with pdfplumber.open(file_path) as pdf:
                        for page_num in blank_pages:
                            page = pdf.pages[page_num - 1]
                            fallback_text = page.extract_text() or ""

                            if fallback_text.strip():
                                page_texts[page_num - 1] = fallback_text

                except Exception as plumber_err:
                    logfire.warning(
                        "pdfplumber fallback failed",
                        error=str(plumber_err),
                    )

            # Preserve original page order
            full_text = "\n\n".join(
                text.strip()
                for text in page_texts
                if text and text.strip()
            )

            if not full_text:
                logfire.warning(
                    "No text extracted; PDF may be image-based",
                    filename=file_path,
                )
            else:
                logfire.info(
                    "PDF text extracted",
                    filename=file_path,
                    characters=len(full_text),
                )

            return full_text

        except Exception as e:
            logfire.error(
                "PDF parsing failed",
                filename=file_path,
                error=str(e),
            )
            raise