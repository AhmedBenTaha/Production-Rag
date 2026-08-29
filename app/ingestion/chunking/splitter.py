from typing import List

import logfire
from langchain_text_splitters import RecursiveCharacterTextSplitter


# Chunking configuration
CHUNK_SIZE = 1500
CHUNK_OVERLAP = 100


def chunk_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[str]:
    """
    Split text into meaningful chunks using recursive character splitting.

    The splitter tries to preserve structure by splitting on:
    paragraphs -> lines -> sentences -> words -> characters.

    Args:
        text: Input text.
        chunk_size: Maximum size of each chunk in characters.
        chunk_overlap: Number of overlapping characters between chunks.

    Returns:
        A list of non-empty text chunks.
    """

    # Validate input
    if not text or not text.strip():
        return []

    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    if chunk_overlap < 0:
        raise ValueError("chunk_overlap cannot be negative")

    if chunk_overlap >= chunk_size:
        raise ValueError(
            "chunk_overlap must be smaller than chunk_size"
        )

    with logfire.span(
        "Text Chunking",
        text_length=len(text),
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    ):
        # Clean unnecessary whitespace
        text = text.strip()

        # Create recursive splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=[
                "\n\n",  # Paragraphs
                "\n",    # Lines
                ". ",    # Sentences
                " ",     # Words
                "",      # Characters
            ],
            length_function=len,
            is_separator_regex=False,
        )

        # Split text
        chunks = splitter.split_text(text)

        # Remove empty chunks
        valid_chunks = [
            chunk.strip()
            for chunk in chunks
            if chunk.strip()
        ]

        logfire.info(
            f"✅ Generated {len(valid_chunks)} chunks "
            f"from {len(text)} characters"
        )

        return valid_chunks