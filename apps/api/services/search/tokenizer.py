import re

def tokenize(text: str) -> list[str]:
    """
    Deterministic code-aware tokenizer.
    Splits by whitespace, punctuation, hyphens, underscores, dots, slashes.
    Also splits camelCase and PascalCase.
    Returns unique lowercase tokens.
    """
    if not text:
        return []

    # Replace common separators with spaces
    text = re.sub(r'[/\\._-]', ' ', text)

    # Split camelCase and PascalCase
    text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)
    text = re.sub(r'([A-Z])([A-Z][a-z])', r'\1 \2', text)

    # Keep alphanumeric tokens
    tokens = []
    for raw_token in text.split():
        cleaned = re.sub(r'[^a-zA-Z0-9]', '', raw_token)
        if cleaned:
            tokens.append(cleaned.lower())

    # Deduplicate while preserving order
    seen = set()
    result = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            result.append(t)

    return result
