# Prompt log (AI-assisted development)

## Goal
Build a data cleaning and validation pipeline that transforms raw scraped data into clean structured output, validates data quality, and generates a quality metrics report.

## Process summary

- Inspected the existing script and found it was not runnable because JSON content was accidentally pasted into a `.py` file.
- Rebuilt the pipeline as a proper Python script:
  - Implemented cleaning helpers: whitespace normalization, HTML tag/entity cleanup, unicode normalization (NFKC), control/invisible character handling, and date parsing to ISO when common date keys exist.
  - Implemented validation: required fields (`title`, `content`, `url`), URL format checks, minimum content length, and explicit failure reasons per record.
  - Implemented quality report: totals, valid/invalid counts, completeness percentage per field, and most common validation failures.
- Added a safe, structured scraping mode for a single Wikipedia page using Wikipedia’s REST summary endpoint (no fragile HTML parsing).
- Refactored code into two modules as required:
  - `cleaner.py` (cleaning + pipeline runner + Wikipedia scrape mode)
  - `validator.py` (validation rules + reason generation)
- Ensured outputs match required filenames:
  - `cleaned_output.json`
  - `quality_report.txt`

## Commands used

- Run local pipeline:
  - `python3 cleaner.py --input sample_data.json`
- Scrape and run pipeline:
  - `python3 cleaner.py --scrape-url "https://en.wikipedia.org/wiki/University_of_Hong_Kong"`

