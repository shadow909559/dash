"""Simple text chunking utilities for RAG."""

from __future__ import annotations

import re
from typing import List


def split_text_into_chunks(text: str, max_chars: int = 1000, overlap: int = 200) -> List[str]:
    """Split text into ordered chunks while preserving paragraph boundaries.

    Strategy:
    - Split on two-or-more newlines into paragraphs.
    - Aggregate paragraphs into chunks until max_chars is reached.
    - If a single paragraph exceeds max_chars, split it by sentences into smaller pieces.
    - Provide an overlap between chunks to preserve context.
    """

    if not text:
        return []

    paragraphs = re.split(r"\n{2,}", text)

    chunks: List[str] = []
    current = ""

    def flush_current():
        nonlocal current
        if current.strip():
            chunks.append(current.strip())
            current = ""

    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        if len(p) > max_chars:
            # split long paragraph into sentences
            sentences = re.split(r'(?<=[\.\?!])\s+', p)
            part = ""
            for s in sentences:
                if len(part) + len(s) + 1 <= max_chars:
                    part = (part + " " + s).strip() if part else s
                else:
                    if part:
                        if current and len(current) + len(part) + 2 <= max_chars:
                            current = (current + "\n\n" + part).strip()
                        else:
                            flush_current()
                            current = part
                        part = s
                    else:
                        # single sentence too long; hard split
                        for i in range(0, len(s), max_chars):
                            piece = s[i : i + max_chars]
                            flush_current()
                            current = piece
                            flush_current()
                        part = ""
            if part:
                if current and len(current) + len(part) + 2 <= max_chars:
                    current = (current + "\n\n" + part).strip()
                else:
                    flush_current()
                    current = part
        else:
            if current and len(current) + len(p) + 2 <= max_chars:
                current = (current + "\n\n" + p).strip()
            else:
                flush_current()
                current = p

    flush_current()

    # apply overlap by repeating last `overlap` chars at start of next chunk
    if overlap and chunks:
        overlapped: List[str] = []
        for i, c in enumerate(chunks):
            if i == 0:
                overlapped.append(c)
            else:
                prev = overlapped[-1]
                take = prev[-overlap:] if overlap < len(prev) else prev
                merged = (take + "\n" + c).strip()
                overlapped.append(merged)
        return overlapped

    return chunks
