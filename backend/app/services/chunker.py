"""Markdown heading-aware chunker.

Strategy:
1. Walk markdown line-by-line, tracking current heading path (H1 > H2 > H3).
2. Accumulate body lines under each heading into a section.
3. If a section exceeds MAX_CHARS, sub-split by paragraphs with small overlap.
4. Skip empty sections. Preserve heading as the first line of the chunk content
   so embeddings capture the semantic context.

Target: 400-800 chars per chunk (works well for Chinese + English mixed wiki).
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

MIN_CHARS = 120        # merge tiny tail chunks into previous
MAX_CHARS = 800        # hard cap before sub-splitting
OVERLAP_CHARS = 80     # overlap between sub-splits of same section

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")


@dataclass
class Chunk:
    position: int
    heading_path: list[str]
    content: str

    @property
    def char_count(self) -> int:
        return len(self.content)


@dataclass
class _Section:
    heading_path: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return "\n".join(self.lines).strip()

    def render(self) -> str:
        parts: list[str] = []
        if self.heading_path:
            # Surface the deepest 1-2 levels to keep chunk header compact
            crumb = " › ".join(self.heading_path[-2:])
            parts.append(f"[{crumb}]")
        if self.body:
            parts.append(self.body)
        return "\n".join(parts).strip()


def _update_path(path: list[str], level: int, title: str) -> list[str]:
    """Truncate path to the new heading level and append the new title."""
    # H1 → index 0, H2 → index 1, etc.
    new_path = path[: level - 1]
    new_path.append(title)
    return new_path


def _split_long_text(text: str, heading_path: list[str], start_pos: int) -> list[Chunk]:
    """Paragraph-aware split with overlap when a section is too long."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    buf: list[str] = []
    buf_len = 0
    pos = start_pos

    def flush(carry: str = "") -> str:
        nonlocal buf, buf_len, pos
        if not buf:
            return ""
        body = "\n\n".join(buf).strip()
        prefix = ""
        if heading_path:
            crumb = " › ".join(heading_path[-2:])
            prefix = f"[{crumb}]\n"
        chunks.append(Chunk(position=pos, heading_path=list(heading_path), content=(prefix + body).strip()))
        pos += 1
        tail = body[-OVERLAP_CHARS:] if OVERLAP_CHARS and len(body) > OVERLAP_CHARS else ""
        buf = [tail] if tail else []
        buf_len = len(tail)
        return tail

    for para in paragraphs:
        if buf_len + len(para) + 2 > MAX_CHARS and buf:
            flush()
        # If a single paragraph is still too big, hard-cut it by char window
        while len(para) > MAX_CHARS:
            piece = para[:MAX_CHARS]
            buf.append(piece)
            buf_len += len(piece)
            flush()
            para = para[MAX_CHARS - OVERLAP_CHARS:]
        buf.append(para)
        buf_len += len(para) + 2
    if buf:
        flush()
    return chunks


def chunk_markdown(content: str, *, title: str | None = None) -> list[Chunk]:
    """Split a markdown string into heading-aware chunks.

    Returns position-indexed chunks, ready for persistence.
    Empty or whitespace-only input yields [].
    """
    if not content or not content.strip():
        return []

    sections: list[_Section] = []
    current = _Section(heading_path=[title] if title else [])

    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        m = HEADING_RE.match(line)
        if m:
            # Close current section
            if current.body:
                sections.append(current)
            level = len(m.group(1))
            heading_title = m.group(2).strip()
            base = [title] if title else []
            # If we keep title as H0, shift: H1 appends to base
            new_path = _update_path(current.heading_path or base, max(1, level), heading_title)
            current = _Section(heading_path=new_path)
        else:
            current.lines.append(raw_line)

    if current.body:
        sections.append(current)

    # Emit chunks, splitting big sections, merging tiny tails
    chunks: list[Chunk] = []
    pos = 0
    for sec in sections:
        rendered = sec.render()
        if not rendered:
            continue
        if len(rendered) <= MAX_CHARS:
            # Merge into the previous chunk if both are tiny
            if chunks and len(rendered) < MIN_CHARS and chunks[-1].heading_path == sec.heading_path:
                prev = chunks[-1]
                prev.content = (prev.content + "\n\n" + rendered).strip()
                continue
            chunks.append(Chunk(position=pos, heading_path=list(sec.heading_path), content=rendered))
            pos += 1
        else:
            sub = _split_long_text(sec.body, sec.heading_path, pos)
            chunks.extend(sub)
            pos += len(sub)

    return chunks
