import pandas as pd
from langdetect import DetectorFactory, LangDetectException, detect

INPUT_PATH = "data/LMU_wide_survey_DE_selected.tab"
OUTPUT_PATH = "data/LMU_wide_survey_DE_selected_preprocessed.tab"

# Make language detection deterministic across runs.
DetectorFactory.seed = 0


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


def is_german_text(text: str) -> bool:
    try:
        return detect(text) == "de"
    except LangDetectException:
        return False


def main() -> None:
    with open(INPUT_PATH, "r") as f:
        df = pd.read_csv(f, sep="\t")

    text_columns = [col for col in df.columns if col != "session_id"]
    normalized_text = df[text_columns].apply(lambda col: col.map(normalize_text))

    non_empty_mask = normalized_text.apply(lambda row: any(row), axis=1)
    df_non_empty = df.loc[non_empty_mask].copy()
    normalized_non_empty = normalized_text.loc[non_empty_mask]

    german_mask = normalized_non_empty.apply(
        lambda row: any(is_german_text(text) for text in row if text), axis=1
    )
    df_german = df_non_empty.loc[german_mask].copy()

    df_german.to_csv(OUTPUT_PATH, sep="\t", index=False)

    print(f"Loaded rows: {len(df)}")
    print(f"Rows after removing empty rows: {len(df_non_empty)}")
    print(f"Rows after keeping German text rows: {len(df_german)}")
    print(f"Wrote preprocessed file: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
