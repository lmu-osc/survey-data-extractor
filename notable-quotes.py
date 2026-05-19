from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from config import TRANSLATABLE_COLUMNS, DEFAULT_INPUT_PATH, DEFAULT_NOTABLE_QUOTES_PATH, DEFAULT_MODEL

load_dotenv()




class QuoteExtraction(BaseModel):
    is_notable: bool = Field(description="Whether this quote is notable given the context")
    sentiment: str = Field(description="Either 'positive', 'negative', or 'neutral'")
    why_notable: str | None = Field(
        default=None, 
        description="Brief explanation of why this quote is notable (if is_notable is True)"
    )
    theme: str | None = Field(
        default=None, 
        description="Main theme of the quote (if is_notable is True): e.g. 'barriers', 'needs', 'support', 'implementation', 'advocacy'"
    )


SYSTEM_PROMPT = """
You are an expert analyst for academic surveys about open science practices.
You are analyzing responses from a university-wide survey at LMU Munich conducted by the Open Science Center (OSC).

CONTEXT:
- The survey aims to understand the wants, needs, and barriers to open science practices
- "Notable" quotes should provide insight into researcher perspectives on open science
- Notable quotes should help understand what researchers value, struggle with, or need from the OSC

WHAT TO LOOK FOR - Notable Quotes:
POSITIVE QUOTES:
- Expressions of support for open science practices
- Recognition of benefits or advantages of open science
- Constructive suggestions for improvement
- Endorsements of specific open science initiatives
- Expressions of willingness to engage

NEGATIVE QUOTES:
- Barriers or obstacles to open science adoption
- Concerns or fears about open science practices
- Lack of support or resources
- Time/workload concerns
- Technical difficulties or unclear guidance
- Skepticism about value or necessity

WHAT TO IGNORE - Not Notable:
- Generic "Yes" or "No" answers
- Incomplete or unclear fragments
- Single words without context
- Purely administrative responses
- Responses that don't relate to open science, research practices, or institutional support

IMPORTANT:
- Be selective: aim for quotes that actually provide meaningful insight
- Quote must be at least a few words to be notable
- Consider the broader institutional context when evaluating
""".strip()


class QuoteRecord(BaseModel):
    session_id: str
    column_name: str
    original_text: str
    sentiment: str
    theme: str
    why_notable: str


def normalize_text(value: object) -> str:
    """Normalize and clean text values from dataframe."""
    if pd.isna(value):
        return ""

    text = str(value).strip()
    if not text:
        return ""

    lowered = text.lower()
    if lowered in {"nan", "none", "null", ""}:
        return ""

    return text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract notable positive and negative quotes from survey responses using an LLM."
    )
    parser.add_argument("--input-path", default=DEFAULT_INPUT_PATH)
    parser.add_argument("--output-path", default=DEFAULT_NOTABLE_QUOTES_PATH)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--fallback-models",
        default="",
        help="Comma-separated list of alternate models to try if the primary model is unavailable.",
    )
    parser.add_argument("--max-attempts", type=int, default=3)
    parser.add_argument("--retry-seconds", type=float, default=2.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.1)
    return parser.parse_args()


def extract_quote_info(agent: Agent, text: str) -> QuoteExtraction | None:
    """Use LLM to determine if a quote is notable and extract its sentiment/theme."""
    try:
        prompt = f"Analyze this survey response and determine if it's a notable quote:\n\n{text}"
        result = agent.run_sync(prompt, output_type=QuoteExtraction)
        return result.output
    except Exception as e:
        print(f"  Error processing quote: {e}")
        return None


def load_data(input_path: Path) -> pd.DataFrame:
    """Load survey data from TSV file."""
    print(f"Loading data from {input_path}...")
    df = pd.read_csv(input_path, sep="\t")
    print(f"Loaded {len(df)} rows and {len(df.columns)} columns")
    return df


def get_all_text_responses(df: pd.DataFrame) -> list[tuple[str, str, str]]:
    """Extract all text responses from survey data.
    
    Returns list of (session_id, column_name, text) tuples, filtering out empty/null values.
    """
    responses = []
    
    for idx, row in df.iterrows():
        session_id = str(row["session_id"]) if "session_id" in df.columns else str(idx)
        
        for col in TRANSLATABLE_COLUMNS:
            if col not in df.columns:
                continue
                
            text = normalize_text(row[col])
            if text:  # Only include non-empty responses
                responses.append((session_id, col, text))
    
    return responses


def setup_agent(model: str, fallback_models: str) -> Agent:
    """Create and configure the extraction agent."""
    return Agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
    )


async def main():
    args = parse_args()
    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    
def main():
    args = parse_args()
    input_path = Path(args.input_path)
    output_path = Path(args.output_path)
    
    # Load data
    df = load_data(input_path)
    responses = get_all_text_responses(df)
    print(f"\nFound {len(responses)} text responses to analyze")
    
    # Setup agent
    agent = setup_agent(args.model, args.fallback_models)
    
    # Extract notable quotes
    notable_quotes: list[QuoteRecord] = []
    print("\nExtracting notable quotes...")
    
    for i, (session_id, col_name, text) in enumerate(responses):
        if (i + 1) % 100 == 0:
            print(f"  Processed {i + 1}/{len(responses)} responses...")
        
        quote_info = None
        for attempt in range(args.max_attempts):
            try:
                quote_info = extract_quote_info(agent, text)
                break
            except ModelHTTPError as e:
                if attempt < args.max_attempts - 1:
                    print(f"    Attempt {attempt + 1} failed, retrying in {args.retry_seconds}s...")
                    time.sleep(args.retry_seconds)
                else:
                    print(f"    Failed after {args.max_attempts} attempts: {e}")
            
            time.sleep(args.sleep_seconds)
        
        if quote_info and quote_info.is_notable:
            record = QuoteRecord(
                session_id=session_id,
                column_name=col_name,
                original_text=text,
                sentiment=quote_info.sentiment,
                theme=quote_info.theme or "other",
                why_notable=quote_info.why_notable or ""
            )
            notable_quotes.append(record)
    
    # Save results
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    results = {
        "metadata": {
            "total_responses_analyzed": len(responses),
            "notable_quotes_found": len(notable_quotes),
            "positive": sum(1 for q in notable_quotes if q.sentiment == "positive"),
            "negative": sum(1 for q in notable_quotes if q.sentiment == "negative"),
            "neutral": sum(1 for q in notable_quotes if q.sentiment == "neutral"),
            "themes": sorted(set(q.theme for q in notable_quotes if q.theme))
        },
        "quotes": [q.model_dump() for q in notable_quotes]
    }
    
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n✓ Results saved to {output_path}")
    print(f"\nSummary:")
    print(f"  Total responses analyzed: {results['metadata']['total_responses_analyzed']}")
    print(f"  Notable quotes found: {results['metadata']['notable_quotes_found']}")
    print(f"  Positive: {results['metadata']['positive']}")
    print(f"  Negative: {results['metadata']['negative']}")
    print(f"  Neutral: {results['metadata']['neutral']}")
    print(f"  Themes: {', '.join(results['metadata']['themes'])}")


if __name__ == "__main__":
    main()