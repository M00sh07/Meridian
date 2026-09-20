"""Deterministic semantic chunking for Phase 4.1.

Produces text chunks for symbols (functions, classes, methods), whole
modules/files, and documentation files. Chunking is fully deterministic:
the same file content and symbols always yield the same chunks in the same
order, with the same ``chunk_key``.

No embeddings, no LLM calls, no retrieval. Chunks are pure derived evidence
that later phases can embed.
"""
import hashlib
import os
from typing import Dict, List, Optional

# Documentation / prose files that become their own module-level chunks.
DOC_EXTENSIONS = {
    '.md', '.markdown', '.rst', '.txt', '.adoc',
}

# Files that should never be chunked as source modules.
SKIP_FILENAMES = {'license', 'licence', 'notice', 'authors', 'contributors'}

# Maps parser symbol types onto chunk types.
SYMBOL_CHUNK_TYPES = {
    'function': 'function',
    'method': 'function',
    'class': 'class',
}


def is_doc_file(path: str) -> bool:
    """Return True when the path should be chunked as documentation."""
    return os.path.splitext(path)[1].lower() in DOC_EXTENSIONS


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode('utf-8')).hexdigest()


def _read_text(file_path: str) -> Optional[str]:
    """Read a file as UTF-8 text, returning None when it is not text-like."""
    try:
        with open(file_path, 'rb') as handle:
            raw = handle.read()
    except OSError:
        return None

    if b'\x00' in raw:
        # Looks binary; skip rather than produce garbage chunks.
        return None

    try:
        text = raw.decode('utf-8')
    except UnicodeDecodeError:
        return None
    # Normalize line endings so chunk content and hashes are identical across
    # platforms (CRLF vs LF) — chunking must be deterministic.
    return text.replace('\r\n', '\n').replace('\r', '\n')


def _slice_lines(lines: List[str], start_line: int, end_line: int) -> str:
    """1-based inclusive line slice, clamped to the available lines."""
    start = max(start_line - 1, 0)
    end = min(end_line, len(lines))
    if start >= end:
        return ''
    return '\n'.join(lines[start:end])


def build_file_chunks(path: str, file_path: str, language: Optional[str],
                      symbols: List[Dict]) -> List[Dict]:
    """Build the ordered chunk list for a single file.

    ``symbols`` entries are dicts with ``id``, ``name``, ``type``,
    ``start_line`` and ``end_line`` — i.e. already-persisted Symbol rows.
    """
    content = _read_text(file_path)
    if content is None:
        return []

    lines = content.splitlines()
    chunks: List[Dict] = []
    is_doc = is_doc_file(path)

    if is_doc:
        # Documentation is chunked as one module-level chunk; it has no symbols.
        text = content.strip()
        if text:
            chunks.append(_make_chunk(
                chunk_type='doc',
                path=path,
                language=language,
                content=text,
                symbol=None,
                start_line=1,
                end_line=len(lines) or 1,
            ))
        return chunks

    # Symbol-level chunks, in the order the parser produced them.
    for symbol in symbols:
        chunk_type = SYMBOL_CHUNK_TYPES.get(symbol.get('type'), 'symbol')
        body = _slice_lines(lines, symbol['start_line'], symbol['end_line'])
        if not body.strip():
            continue
        chunks.append(_make_chunk(
            chunk_type=chunk_type,
            path=path,
            language=language,
            content=body,
            symbol=symbol,
            start_line=symbol['start_line'],
            end_line=symbol['end_line'],
        ))

    # Module-level chunk for the whole file, so symbols are always reachable
    # through their containing file as well.
    module_text = content.strip()
    if module_text:
        chunks.append(_make_chunk(
            chunk_type='module',
            path=path,
            language=language,
            content=module_text,
            symbol=None,
            start_line=1,
            end_line=len(lines) or 1,
        ))

    return chunks


def _make_chunk(chunk_type: str, path: str, language: Optional[str],
                content: str, symbol: Optional[Dict],
                start_line: int, end_line: int) -> Dict:
    """Assemble a chunk dict with a stable identity key."""
    symbol_name = symbol['name'] if symbol else None
    symbol_type = symbol['type'] if symbol else None

    if symbol:
        chunk_key = f"{chunk_type}:{path}:{symbol_name}:{start_line}-{end_line}"
    else:
        chunk_key = f"{chunk_type}:{path}"

    return {
        'chunk_key': chunk_key,
        'chunk_type': chunk_type,
        'path': path,
        'symbol_id': symbol['id'] if symbol else None,
        'symbol_name': symbol_name,
        'symbol_type': symbol_type,
        'language': language,
        'start_line': start_line,
        'end_line': end_line,
        'content': content,
        'content_hash': _hash_content(content),
    }
