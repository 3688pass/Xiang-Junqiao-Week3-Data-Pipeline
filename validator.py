from __future__ import annotations

from typing import Any, Dict, Iterable, List, Tuple
import html
import re
import unicodedata
from urllib.parse import urlparse


REQUIRED_FIELDS = ("title", "content", "url")

_WHITESPACE_RE = re.compile(r"\s+")


def _to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def normalize_text(value: Any) -> str:
    """Lightweight normalization to match cleaning/validation expectations."""
    s = _to_text(value)
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\ufeff", "").replace("\u200b", "").replace("\u00a0", " ")
    s = "".join(ch for ch in s if (ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"))
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def is_valid_url(url: str) -> bool:
    """Validate URL format (http/https + netloc)."""
    if not url:
        return False
    try:
        u = urlparse(url)
    except Exception:
        return False
    return u.scheme in ("http", "https") and bool(u.netloc)


def validate_record(record: Dict[str, Any], *, min_content_length: int = 10) -> List[str]:
    """Return validation failure reasons (empty list means valid)."""
    reasons: List[str] = []

    # Required fields
    for f in REQUIRED_FIELDS:
        if not normalize_text(record.get(f)):
            reasons.append(f"missing_required_field:{f}")

    # URL format
    url = normalize_text(record.get("url"))
    if url and not is_valid_url(url):
        reasons.append("invalid_url_format")

    # Content minimum length
    content = normalize_text(record.get("content"))
    if content and len(content) < min_content_length:
        reasons.append(f"content_too_short:min_{min_content_length}")

    return reasons


def validate_data(
    records: Iterable[Dict[str, Any]],
    *,
    min_content_length: int = 10,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """
    Validate records.
    Returns (valid_records, invalid_records_with_reasons, flat_reason_list)
    """
    valid: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    reasons_flat: List[str] = []

    for idx, record in enumerate(records):
        reasons = validate_record(record, min_content_length=min_content_length)
        if reasons:
            invalid.append({"index": idx, "record": record, "reasons": reasons})
            reasons_flat.extend(reasons)
        else:
            valid.append(record)

    return valid, invalid, reasons_flat

