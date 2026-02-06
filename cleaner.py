from __future__ import annotations

import argparse
import html
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen

from validator import REQUIRED_FIELDS, validate_data


"""
Data cleaning + validation pipeline.

Files in this assignment:
- cleaner.py: cleaning + pipeline runner
- validator.py: validation rules
- sample_data.json: sample raw input
- cleaned_output.json: cleaned valid output
- quality_report.txt: metrics report
"""


MIN_CONTENT_LENGTH = 10
DEFAULT_INPUT_PATH = "sample_data.json"
DEFAULT_CLEAN_OUTPUT_PATH = "cleaned_output.json"
DEFAULT_REPORT_PATH = "quality_report.txt"

# Common date keys found in scraped data; if present we normalize to ISO 8601.
DATE_KEYS = (
    "date",
    "published_date",
    "published_at",
    "created_at",
    "updated_at",
    "timestamp",
    "time",
)


# -----------------------------
# Cleaning
# -----------------------------
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _to_text(value: Any) -> str:
    """Convert unknown types to text safely."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def normalize_text(value: Any) -> str:
    """
    Normalize text encoding and special characters:
    - HTML entities unescape (e.g., &nbsp; &amp;)
    - Unicode NFKC normalization
    - remove invisible/control chars (keep tab/newline)
    - collapse whitespace
    """
    s = _to_text(value)
    s = html.unescape(s)
    s = unicodedata.normalize("NFKC", s)

    # Common invisible chars
    s = s.replace("\ufeff", "")  # BOM
    s = s.replace("\u200b", "")  # zero-width space
    s = s.replace("\u00a0", " ")  # non-breaking space -> normal space

    # Remove control characters except \n \t
    s = "".join(ch for ch in s if (ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"))

    # Normalize line endings and whitespace
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = _WHITESPACE_RE.sub(" ", s).strip()
    return s


def remove_html_artifacts(value: Any) -> str:
    """Remove HTML tags and normalize leftover text."""
    s = _to_text(value)
    s = html.unescape(s)
    s = _HTML_TAG_RE.sub(" ", s)
    return normalize_text(s)


def parse_date_to_iso(value: Any) -> Optional[str]:
    """
    Standardize date formats to ISO format (ISO 8601).
    Returns None if parsing fails or value is empty.
    """
    if value is None:
        return None

    # Epoch timestamps
    if isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(float(value), tz=timezone.utc)
            return dt.isoformat()
        except Exception:
            return None

    s = normalize_text(value)
    if not s:
        return None

    # Try ISO first
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.isoformat()
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass

    patterns = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y.%m.%d",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M",
        "%Y/%m/%d %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%b %d, %Y",
        "%B %d, %Y",
    ]
    for p in patterns:
        try:
            dt = datetime.strptime(s, p)
            if p in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"):
                return dt.date().isoformat()
            return dt.isoformat()
        except Exception:
            continue

    return None


def clean_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Clean one raw record into a normalized dict."""
    cleaned: Dict[str, Any] = dict(record)

    if "title" in cleaned:
        cleaned["title"] = remove_html_artifacts(cleaned.get("title"))
    if "content" in cleaned:
        cleaned["content"] = remove_html_artifacts(cleaned.get("content"))
    if "url" in cleaned:
        cleaned["url"] = normalize_text(cleaned.get("url"))

    # Normalize dates if present
    for k in DATE_KEYS:
        if k in cleaned:
            iso = parse_date_to_iso(cleaned.get(k))
            cleaned[k] = iso if iso is not None else normalize_text(cleaned.get(k))

    # Normalize other string-like fields
    for k, v in list(cleaned.items()):
        if k in ("title", "content", "url"):
            continue
        if isinstance(v, (str, bytes)):
            cleaned[k] = normalize_text(v)

    return cleaned


def clean_data(records: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [clean_record(r) for r in records]


# -----------------------------
# Quality report
# -----------------------------
def _completeness_percent(records: List[Dict[str, Any]], field: str) -> float:
    total = len(records)
    if total == 0:
        return 0.0
    present = sum(1 for r in records if normalize_text(r.get(field)))
    return present / total * 100.0


def generate_report(
    processed_records: List[Dict[str, Any]],
    valid_records: List[Dict[str, Any]],
    invalid_records: List[Dict[str, Any]],
    reason_list: List[str],
    *,
    top_n_failures: int = 5,
) -> str:
    """Generate the quality report text (saved to quality_report.txt)."""
    total = len(processed_records)
    valid_count = len(valid_records)
    invalid_count = len(invalid_records)

    completeness = {f: _completeness_percent(processed_records, f) for f in REQUIRED_FIELDS}
    reason_counts = Counter(reason_list)

    lines: List[str] = []
    lines.append("=" * 60)
    lines.append("Data Quality Report")
    lines.append("=" * 60)
    lines.append(f"Generated at (UTC): {datetime.now(timezone.utc).isoformat()}")
    lines.append("")
    lines.append("Summary")
    lines.append("-" * 60)
    lines.append(f"Total records processed: {total}")
    lines.append(f"Valid records: {valid_count}")
    lines.append(f"Invalid records: {invalid_count}")
    lines.append(f"Valid rate: {(valid_count / total * 100.0):.1f}%" if total else "Valid rate: 0.0%")
    lines.append("")
    lines.append("Completeness by field (%)")
    lines.append("-" * 60)
    for f in REQUIRED_FIELDS:
        lines.append(f"{f:10s}: {completeness.get(f, 0.0):5.1f}%")
    lines.append("")
    lines.append("Common validation failures")
    lines.append("-" * 60)
    if reason_counts:
        for reason, count in reason_counts.most_common(top_n_failures):
            lines.append(f"{reason}: {count}")
    else:
        lines.append("None")
    lines.append("=" * 60)

    return "\n".join(lines)


# -----------------------------
# Scraping (Wikipedia)
# -----------------------------
def _http_get_json(url: str, *, timeout_seconds: int = 20) -> Any:
    req = Request(
        url,
        headers={
            "User-Agent": "assignment1-cleaner/1.0 (educational)",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(req, timeout=timeout_seconds) as resp:  # nosec - educational script
        raw = resp.read()
    return json.loads(raw.decode("utf-8", errors="replace"))


def scrape_wikipedia_article(url: str) -> Dict[str, Any]:
    """Scrape one en.wikipedia.org article into a raw record."""
    parsed = urlparse(url)
    if parsed.netloc not in ("en.wikipedia.org", "www.en.wikipedia.org"):
        raise ValueError("Only supports en.wikipedia.org URLs.")
    if not parsed.path.startswith("/wiki/"):
        raise ValueError("Wikipedia article URL must start with /wiki/.")

    title = parsed.path[len("/wiki/") :]
    api_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
    summary = _http_get_json(api_url)

    return {
        "title": summary.get("title") or title.replace("_", " "),
        "content": summary.get("extract") or "",
        "url": (summary.get("content_urls") or {}).get("desktop", {}).get("page") or url,
        "source": "wikipedia",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "lang": "en",
    }


# -----------------------------
# IO / Pipeline runner
# -----------------------------
def load_json_records(path: str) -> List[Dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("Input JSON must be a list of records (objects).")
    records: List[Dict[str, Any]] = []
    for i, item in enumerate(data):
        if isinstance(item, dict):
            records.append(item)
        else:
            records.append({"_raw": item, "_error": f"non_object_record_at_index_{i}"})
    return records


def run_pipeline_from_records(raw_records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], str]:
    cleaned = clean_data(raw_records)
    valid, invalid, reasons = validate_data(cleaned, min_content_length=MIN_CONTENT_LENGTH)
    report_text = generate_report(cleaned, valid, invalid, reasons)
    return cleaned, valid, report_text


def save_outputs(valid_records: List[Dict[str, Any]], report_text: str) -> None:
    with open(DEFAULT_CLEAN_OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(valid_records, f, ensure_ascii=False, indent=2)

    with open(DEFAULT_REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report_text)


def main() -> None:
    parser = argparse.ArgumentParser(description="Data cleaning + validation pipeline")
    parser.add_argument("--input", default=DEFAULT_INPUT_PATH, help="Path to raw scraped JSON (list of objects)")
    parser.add_argument("--scrape-url", default=None, help="Scrape a single Wikipedia URL (en.wikipedia.org)")
    args = parser.parse_args()

    if args.scrape_url:
        raw_records = [scrape_wikipedia_article(args.scrape_url)]
    else:
        raw_records = load_json_records(args.input)

    _, valid, report_text = run_pipeline_from_records(raw_records)
    save_outputs(valid, report_text)

    print("Pipeline complete.")
    print(f"Saved: {DEFAULT_CLEAN_OUTPUT_PATH}, {DEFAULT_REPORT_PATH}")


if __name__ == "__main__":
    main()

