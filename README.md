# Assignment 1: Data Cleaning & Validation Pipeline

This project builds a small pipeline that turns raw scraped records into clean, structured output and generates a data-quality report.

## Files

- `cleaner.py`: data cleaning implementation + pipeline runner (also supports scraping one Wikipedia article)
- `validator.py`: validation rules (required fields, URL format, minimum content length)
- `sample_data.json`: sample raw input data
- `cleaned_output.json`: cleaned output (only **valid** records)
- `quality_report.txt`: generated quality report
- `prompt-log.md`: AI-assisted development log

## Requirements Covered

- **Cleaning**: whitespace + HTML artifacts removal, unicode normalization, special character handling, date normalization to ISO (if date-like keys exist)
- **Validation**: required fields (`title`, `content`, `url`), URL format, minimum content length, invalid reasons
- **Quality report**: totals, valid/invalid counts, completeness per field, common validation failures

## How to Run

### 1) Run on local JSON input

```bash
python3 cleaner.py --input sample_data.json
```

### 2) Scrape a Wikipedia article (single page)

```bash
python3 cleaner.py --scrape-url "https://en.wikipedia.org/wiki/University_of_Hong_Kong"
```

## Outputs

After running, you will get:

- `cleaned_output.json`
- `quality_report.txt`

