from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError

from config import TRANSLATABLE_COLUMNS, DEFAULT_INPUT_PATH, DEFAULT_OUTPUT_PATH, DEFAULT_MAP_OUTPUT_PATH, DEFAULT_CACHE_PATH, DEFAULT_MODEL




class BatchInputItem(BaseModel):
    key: str
    text: str


class BatchOutputItem(BaseModel):
    key: str
    english: str


class BatchOutput(BaseModel):
    items: list[BatchOutputItem]


SYSTEM_PROMPT = """
You are an expert translator for survey responses.
Translate German text to natural, concise English while preserving meaning.
Rules:
- Keep short fragments short.
- Keep URLs exactly as-is.
- Keep punctuation and emphasis where possible.
- If input text is already English, return it unchanged.
- Return one output item per input key.
""".strip()


def normalize_text(value: object) -> str:
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered in {"nan", "none", "null"}:
        return ""

    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Translate selected TSV columns from German to English using an LLM."
    )
    parser.add_argument("--input-path", default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-path", default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--map-output-path", default=DEFAULT_MAP_OUTPUT_PATH)
    parser.add_argument("--cache-path", default=DEFAULT_CACHE_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--fallback-models",
        default="",
        help="Comma-separated list of alternate models to try if the primary model is unavailable.",
    )
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-seconds", type=float, default=2.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.2)
    return parser.parse_args()


def load_cache(cache_path: Path) -> dict[str, str]:
    if not cache_path.exists():
        return {}

    with cache_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Cache file is not a JSON object: {cache_path}")

    return {str(k): str(v) for k, v in data.items()}


def save_cache(cache_path: Path, cache: dict[str, str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def build_agent(model_name: str) -> Agent:
    return Agent(
        model=model_name,
        system_prompt=SYSTEM_PROMPT,
    )


def translate_batch(
    agent: Agent,
    items: list[BatchInputItem],
    max_attempts: int,
    retry_seconds: float,
    model_name: str,
    fallback_models: list[str],
) -> tuple[dict[str, str], Agent]:
    keys = [item.key for item in items]
    payload = {
        "items": [item.model_dump() for item in items],
        "instruction": "Return only translated items with the same keys.",
    }
    prompt = json.dumps(payload, ensure_ascii=False)

    attempt = 1
    while attempt <= max_attempts:
        try:
            result = agent.run_sync(prompt, output_type=BatchOutput)
            output_obj = result.output
            if isinstance(output_obj, str):
                try:
                    parsed = json.loads(output_obj)
                except Exception:
                    raise ValueError("Agent returned non-JSON text output; cannot parse translations.")
                items_list = parsed.get("items", [])
                translated = {
                    it["key"]: str(it.get("english", "")).strip()
                    for it in items_list
                    if str(it.get("english", "")).strip()
                }
            else:
                translated = {
                    item.key: item.english.strip()
                    for item in output_obj.items
                    if item.english.strip()
                }
            expected = set(keys)
            received = set(translated.keys())
            if expected != received:
                missing = sorted(expected - received)
                extra = sorted(received - expected)
                raise ValueError(
                    f"Batch key mismatch. Missing={missing}, Extra={extra}"
                )
            return translated, agent
        except ModelHTTPError as e:
            # Model service unavailable (e.g., high demand). Retry with backoff,
            # then try fallback models if provided.
            if getattr(e, "status_code", None) == 503:
                if attempt < max_attempts:
                    backoff = retry_seconds * (2 ** (attempt - 1))
                    time.sleep(backoff)
                    attempt += 1
                    continue

                # exhausted attempts for this model; try fallbacks
                for fb in fallback_models:
                    try:
                        new_agent = build_agent(fb)
                        result = new_agent.run_sync(prompt, output_type=BatchOutput)
                        output_obj = result.output
                        if isinstance(output_obj, str):
                            try:
                                parsed = json.loads(output_obj)
                            except Exception:
                                raise ValueError(
                                    "Agent returned non-JSON text output from fallback; cannot parse translations."
                                )
                            items_list = parsed.get("items", [])
                            translated = {
                                it["key"]: str(it.get("english", "")).strip()
                                for it in items_list
                                if str(it.get("english", "")).strip()
                            }
                        else:
                            translated = {
                                item.key: item.english.strip()
                                for item in output_obj.items
                                if item.english.strip()
                            }
                        expected = set(keys)
                        received = set(translated.keys())
                        if expected != received:
                            missing = sorted(expected - received)
                            extra = sorted(received - expected)
                            raise ValueError(
                                f"Batch key mismatch. Missing={missing}, Extra={extra}"
                            )
                        return translated, new_agent
                    except ModelHTTPError:
                        continue

            # re-raise for other model errors
            raise
        except Exception:
            if attempt == max_attempts:
                raise
            time.sleep(retry_seconds)
            attempt += 1

    raise RuntimeError("Translation batch failed unexpectedly.")


def main() -> None:
    load_dotenv()

    args = parse_args()
    fallback_models = [m.strip() for m in args.fallback_models.split(",") if m.strip()]

    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    map_output_path = Path(args.map_output_path)
    cache_path = Path(args.cache_path)

    with input_path.open("r", encoding="utf-8") as f:
        df = pd.read_csv(f, sep="\t")

    if "session_id" not in df.columns:
        raise ValueError("Input file must contain a 'session_id' column.")

    translatable_columns = [c for c in TRANSLATABLE_COLUMNS if c in df.columns]
    if not translatable_columns:
        raise ValueError("No configured translatable columns were found in input.")

    long_df = df[["session_id", *translatable_columns]].melt(
        id_vars="session_id",
        var_name="column_name",
        value_name="source_text",
    )
    long_df["source_text"] = long_df["source_text"].map(normalize_text)
    long_df = long_df[long_df["source_text"] != ""].copy()

    if long_df.empty:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        map_output_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(output_path, sep="\t", index=False)
        long_df.assign(translated_text="").to_csv(map_output_path, sep="\t", index=False)
        print("No non-empty translatable cells found. Wrote pass-through outputs.")
        return

    long_df["cell_key"] = (
        long_df["session_id"].astype(str) + "::" + long_df["column_name"].astype(str)
    )

    cache = load_cache(cache_path)
    unique_texts = sorted(set(long_df["source_text"]))
    texts_to_translate = [text for text in unique_texts if text not in cache]

    print(f"Cells to translate: {len(long_df)}")
    print(f"Unique snippets: {len(unique_texts)}")
    print(f"Cache hits: {len(unique_texts) - len(texts_to_translate)}")
    print(f"Cache misses: {len(texts_to_translate)}")

    if texts_to_translate:
        try:
            agent = build_agent(args.model)
        except ModelHTTPError as e:
            # Try fallbacks if provided
            if fallback_models:
                agent = None
                for fb in fallback_models:
                    try:
                        agent = build_agent(fb)
                        print(f"Using fallback model: {fb}")
                        break
                    except ModelHTTPError:
                        continue
                if agent is None:
                    raise RuntimeError(
                        f"Primary model '{args.model}' unavailable and no fallback succeeded: {e}"
                    )
            else:
                raise RuntimeError(
                    f"Model '{args.model}' unavailable: {e}. Pass --fallback-models or --model to use another model."
                )
        for start in range(0, len(texts_to_translate), args.batch_size):
            batch_texts = texts_to_translate[start : start + args.batch_size]
            items = [
                BatchInputItem(key=f"t{i}", text=text)
                for i, text in enumerate(batch_texts)
            ]
            translated_by_key, agent = translate_batch(
                agent=agent,
                items=items,
                max_attempts=args.max_attempts,
                retry_seconds=args.retry_seconds,
                model_name=args.model,
                fallback_models=fallback_models,
            )
            for i, source_text in enumerate(batch_texts):
                cache[source_text] = translated_by_key[f"t{i}"]

            done = min(start + args.batch_size, len(texts_to_translate))
            print(f"Translated unique snippets: {done}/{len(texts_to_translate)}")
            if args.sleep_seconds > 0:
                time.sleep(args.sleep_seconds)

    save_cache(cache_path, cache)

    long_df["translated_text"] = long_df["source_text"].map(cache)
    if long_df["translated_text"].isna().any():
        missing_count = int(long_df["translated_text"].isna().sum())
        raise ValueError(f"Missing translations for {missing_count} cells.")

    translated_df = df.copy()
    for column in translatable_columns:
        normalized_col = translated_df[column].map(normalize_text)
        non_empty_mask = normalized_col != ""
        translated_values = normalized_col[non_empty_mask].map(cache)
        # Ensure the column can hold string values without casting errors
        if translated_df[column].dtype != object:
            translated_df[column] = translated_df[column].astype(object)
        # Coerce non-string mapped values to string
        translated_df.loc[non_empty_mask, column] = (
            translated_values.fillna("").map(str).to_numpy(dtype=object)
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    map_output_path.parent.mkdir(parents=True, exist_ok=True)
    translated_df.to_csv(output_path, sep="\t", index=False)

    long_df[
        ["cell_key", "session_id", "column_name", "source_text", "translated_text"]
    ].to_csv(map_output_path, sep="\t", index=False)

    print(f"Wrote translated table: {output_path}")
    print(f"Wrote cell mapping table: {map_output_path}")
    print(f"Updated translation cache: {cache_path}")


if __name__ == "__main__":
    main()
