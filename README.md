# Translate German Survey Text with an LLM

This repository includes a script that translates configured text columns from German to English while preserving table structure and joinability.

## Quick Overview

### Main Processing

1. `select-vars.py` takes the original dataset, and removes all columns that are not the session_id or the target columns for translation
2. `preprocessing.py` removes rows that are fully empty and rows that do not have *any* German text detected at all
3. `translate_with_llm.py` is large, but in short, it sends the cells to an LLM API for translation, caches results, and closes by reconstructing the results into a data frame/file with the same structure as the input data.

### Notable Quote Extraction

1. `notable-quotes.py` uses the preprocessed data to then extract notable quotes from the free text responses (untranslated).

## Details

### What it produces

- `data/LMU_wide_survey_DE_selected_translated.tab`
	- Same row/column layout as the input.
	- `row_number` is preserved.
	- Only configured translatable columns are replaced with translated text.
- `data/LMU_wide_survey_DE_selected_translation_map.tab`
	- One row per translated cell with:
		- `cell_key` (`row_number::column_name`)
		- `row_number`
		- `column_name`
		- `source_text`
		- `translated_text`
- `data/translation_cache.json`
	- Caches translations by exact source snippet to reduce API cost on re-runs.

### Why this is efficient

- It translates unique snippets only, not every repeated cell.
- It batches snippets into one LLM call per batch.
- It reuses a JSON cache across runs.

### Install dependencies

```bash
uv sync
```

### Set your API key

For Gemini models:

The script loads `.env` automatically, so you can keep the key in a local `.env` file as `GOOGLE_API_KEY=...`.

```bash
export GOOGLE_API_KEY="your_api_key_here"
```

### Run translation

```bash
# just use presets
uv run translate_with_llm.py 

# or specify arguments to customize e.g. model, batch size, file names, etc.
# 
uv run translate_with_llm.py \
	--input-path data/LMU_wide_survey_DE_selected_preprocessed.xlsx \
	--output-path data/LMU_wide_survey_DE_selected_translated.xlsx \
	--map-output-path data/LMU_wide_survey_DE_selected_translation_map.xlsx \
	--cache-path data/translation_cache.json \
	--model google:gemini-3.1-flash-lite \
	--batch-size 25
```

### Notes

- Translatable columns are defined in `config.py` (`TRANSLATABLE_COLUMNS`).
- If a configured column is missing in the input, it is skipped.
- Empty cells remain empty.
- If a text is already English, the prompt asks the model to keep it unchanged.

### Reconnect translated text to original data

You can reconnect using either:

- The wide translated output (`row_number` + same columns).
- The mapping file via `(row_number, column_name)` or `cell_key`.
