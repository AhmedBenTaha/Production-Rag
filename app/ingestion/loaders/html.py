from bs4 import BeautifulSoup
import logfire


def parse_html(file_path: str) -> str:
    """
    Parse HTML content using BeautifulSoup.

    Removes non-readable elements and extracts clean text
    suitable for downstream RAG processing.
    """
    with logfire.span("HTML Parsing", filename=file_path):
        try:
            with open(
                file_path,
                "r",
                encoding="utf-8",
                errors="ignore",
            ) as f:
                content = f.read()

            soup = BeautifulSoup(content, "html.parser")

            # Remove non-content elements
            for element in soup(
                ["script", "style", "meta", "noscript"]
            ):
                element.decompose()

            # Extract visible text
            text = soup.get_text(separator="\n")

            # Clean whitespace
            lines = (line.strip() for line in text.splitlines())
            chunks = (
                phrase.strip()
                for line in lines
                for phrase in line.split("  ")
            )

            text_clean = "\n".join(
                chunk for chunk in chunks if chunk
            )

            return text_clean

        except Exception as e:
            logfire.error(
                "HTML parsing failed",
                error=str(e),
                filename=file_path,
            )
            raise