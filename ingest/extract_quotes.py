"""Extract representative quotes from literary works and online quote sources.

Usage:
  python -m ingest.extract_quotes                     # extract for all personas
  python -m ingest.extract_quotes --persona eminescu   # single persona
"""

import asyncio
import hashlib
import json
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings


# Minimum character length for a substantive quote
MIN_QUOTE_LENGTH = 20
MAX_QUOTE_LENGTH = 500


def _content_hash(text: str) -> str:
    """Generate a hash for deduplication."""
    return hashlib.md5(text.strip().lower().encode()).hexdigest()


def sanitize_quote(text: str) -> str:
    """Clean up a quote string."""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    # Remove quotation marks at start/end
    text = text.strip('""\u201c\u201d\u201e\u201f\xab\xbb\'')
    return text.strip()


# ---------------------------------------------------------------------------
# Extract quotes from scraped literary works
# ---------------------------------------------------------------------------

def extract_quotes_from_works(persona_id: str) -> list[dict]:
    """Extract memorable passages from scraped literary works.

    Strategy varies by persona:
    - Poetry (Eminescu): extract complete short poems, famous stanzas
    - Drama (Caragiale): extract memorable dialogue lines
    - Philosophy (Cioran, Eliade): extract aphoristic sentences
    - Speeches (Bratianu): extract key declarative sentences
    """
    works_dir = Path(settings.data_dir) / persona_id / "works"
    if not works_dir.exists():
        return []

    quotes = []

    for work_file in sorted(works_dir.glob("*.md")):
        text = work_file.read_text(encoding="utf-8", errors="replace")
        # Skip the metadata header (first 3 lines: title, blank, source)
        lines = text.split("\n")
        if len(lines) > 3 and lines[0].startswith("#"):
            text = "\n".join(lines[3:])

        extracted = _extract_memorable_passages(text, work_file.name, persona_id)
        quotes.extend(extracted)

    return quotes


def _extract_memorable_passages(text: str, source_file: str, persona_id: str) -> list[dict]:
    """Extract memorable passages using persona-appropriate strategies."""
    passages = []

    if persona_id in ("eminescu",):
        # Poetry: extract stanzas (separated by double newlines)
        passages = _extract_stanzas(text, source_file)
    elif persona_id in ("caragiale",):
        # Drama: extract dialogue lines and witty observations
        passages = _extract_dialogue_and_wit(text, source_file)
    elif persona_id in ("cioran",):
        # Aphoristic philosophy: extract short punchy sentences
        passages = _extract_aphorisms(text, source_file)
    elif persona_id in ("eliade",):
        # Mixed: aphoristic passages + narrative wisdom
        passages = _extract_philosophical_passages(text, source_file)
    elif persona_id in ("bratianu",):
        # Speeches: extract declarative statements
        passages = _extract_declarative_statements(text, source_file)

    return passages


def _extract_stanzas(text: str, source_file: str) -> list[dict]:
    """Extract poetic stanzas (blocks of text separated by blank lines)."""
    quotes = []
    blocks = re.split(r"\n\s*\n", text)

    for block in blocks:
        block = block.strip()
        if MIN_QUOTE_LENGTH <= len(block) <= MAX_QUOTE_LENGTH * 2:
            # Check if it looks like verse (has line breaks)
            if "\n" in block:
                quotes.append({
                    "text": block,
                    "source_file": source_file,
                    "source_type": "literary_stanza",
                    "char_count": len(block),
                })

    return quotes


def _extract_dialogue_and_wit(text: str, source_file: str) -> list[dict]:
    """Extract dialogue lines and witty observations from dramatic works."""
    quotes = []
    # Match lines that look like dramatic dialogue (CHARACTER_NAME. text or CHARACTER_NAME: text)
    dialogue_pattern = re.compile(r"^([A-ZĂÂÎȘȚ][A-ZĂÂÎȘȚ\s]+)[.:]\s*(.+)$", re.MULTILINE)

    for match in dialogue_pattern.finditer(text):
        line = match.group(2).strip()
        if MIN_QUOTE_LENGTH <= len(line) <= MAX_QUOTE_LENGTH:
            speaker = match.group(1).strip()
            quotes.append({
                "text": f"{speaker}: {line}",
                "source_file": source_file,
                "source_type": "dramatic_dialogue",
                "char_count": len(line),
            })

    # Also extract standalone sentences with satirical/witty markers
    sentences = re.split(r'[.!?]+', text)
    for sent in sentences:
        sent = sent.strip()
        if MIN_QUOTE_LENGTH <= len(sent) <= MAX_QUOTE_LENGTH:
            quotes.append({
                "text": sent,
                "source_file": source_file,
                "source_type": "literary_excerpt",
                "char_count": len(sent),
            })

    return quotes


def _extract_aphorisms(text: str, source_file: str) -> list[dict]:
    """Extract aphoristic sentences (short, punchy, self-contained)."""
    quotes = []
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sent in sentences:
        sent = sent.strip()
        # Aphorisms are typically short and self-contained
        if MIN_QUOTE_LENGTH <= len(sent) <= MAX_QUOTE_LENGTH:
            quotes.append({
                "text": sent,
                "source_file": source_file,
                "source_type": "aphorism",
                "char_count": len(sent),
            })

    return quotes


def _extract_philosophical_passages(text: str, source_file: str) -> list[dict]:
    """Extract philosophical passages — sentences and short paragraphs."""
    quotes = []
    # Paragraphs first
    paragraphs = re.split(r"\n\s*\n", text)
    for para in paragraphs:
        para = para.strip()
        if MIN_QUOTE_LENGTH <= len(para) <= MAX_QUOTE_LENGTH:
            quotes.append({
                "text": para,
                "source_file": source_file,
                "source_type": "philosophical_passage",
                "char_count": len(para),
            })

    # Also individual sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    for sent in sentences:
        sent = sent.strip()
        if MIN_QUOTE_LENGTH <= len(sent) <= MAX_QUOTE_LENGTH:
            quotes.append({
                "text": sent,
                "source_file": source_file,
                "source_type": "philosophical_passage",
                "char_count": len(sent),
            })

    return quotes


def _extract_declarative_statements(text: str, source_file: str) -> list[dict]:
    """Extract declarative statements from political speeches."""
    quotes = []
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sent in sentences:
        sent = sent.strip()
        if MIN_QUOTE_LENGTH <= len(sent) <= MAX_QUOTE_LENGTH:
            quotes.append({
                "text": sent,
                "source_file": source_file,
                "source_type": "speech_excerpt",
                "char_count": len(sent),
            })

    return quotes


# ---------------------------------------------------------------------------
# Scrape quotes from online quote sites
# ---------------------------------------------------------------------------

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}

WIKIQUOTE_URLS = {
    "eminescu": "https://en.wikiquote.org/wiki/Mihai_Eminescu",
    "caragiale": "https://en.wikiquote.org/wiki/Ion_Luca_Caragiale",
    "cioran": "https://en.wikiquote.org/wiki/Emil_Cioran",
    "eliade": "https://en.wikiquote.org/wiki/Mircea_Eliade",
}


async def scrape_wikiquote(client: httpx.AsyncClient, persona_id: str) -> list[dict]:
    """Scrape quotes from Wikiquote (CC-licensed)."""
    url = WIKIQUOTE_URLS.get(persona_id)
    if not url:
        return []

    try:
        resp = await client.get(url, follow_redirects=True)
        if resp.status_code != 200:
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        content = soup.find("div", {"class": "mw-parser-output"})
        if not content:
            return []

        quotes = []
        for li in content.find_all("li"):
            text = li.get_text(strip=True)
            text = sanitize_quote(text)
            if MIN_QUOTE_LENGTH <= len(text) <= MAX_QUOTE_LENGTH * 2:
                quotes.append({
                    "text": text,
                    "source_file": f"wikiquote_{persona_id}",
                    "source_type": "wikiquote",
                    "char_count": len(text),
                })

        return quotes
    except Exception as e:
        print(f"  Error scraping Wikiquote for {persona_id}: {e}")
        return []


# ---------------------------------------------------------------------------
# Main extraction pipeline
# ---------------------------------------------------------------------------

def save_quotes(quotes: list[dict], output_path: Path):
    """Save quotes to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        for q in quotes:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"  Saved {len(quotes)} quotes to {output_path}")


async def extract_for_persona(persona_id: str):
    """Extract all quotes for a single persona."""
    from personas import get_persona

    persona = get_persona(persona_id)
    print(f"\n{'=' * 60}")
    print(f"EXTRACTING QUOTES: {persona.display_name} ({persona_id})")
    print(f"{'=' * 60}")

    all_quotes = []
    seen_hashes = set()

    def add_unique(quotes: list[dict]):
        added = 0
        for q in quotes:
            h = _content_hash(q["text"])
            if h not in seen_hashes:
                seen_hashes.add(h)
                all_quotes.append(q)
                added += 1
        return added

    # Step 1: Extract from scraped works
    print("\n  --- From literary works ---")
    work_quotes = extract_quotes_from_works(persona_id)
    added = add_unique(work_quotes)
    print(f"  Extracted {len(work_quotes)} passages, {added} unique")

    # Step 2: Baked-in representative quotes from persona config
    print("\n  --- From persona configuration ---")
    baked_quotes = []
    for q_text in persona.representative_quotes:
        baked_quotes.append({
            "text": q_text,
            "source_file": f"{persona_id}_representative",
            "source_type": "curated_quote",
            "char_count": len(q_text),
        })
    added = add_unique(baked_quotes)
    print(f"  {added} curated quotes from persona config")

    # Step 3: Read scraped quotes (from scraper.py)
    print("\n  --- From scraped quotes ---")
    scraped_file = Path(settings.data_dir) / persona_id / "quotes" / "scraped_quotes.jsonl"
    if scraped_file.exists():
        scraped_quotes = []
        with open(scraped_file, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    scraped_quotes.append(json.loads(line))
        added = add_unique(scraped_quotes)
        print(f"  {len(scraped_quotes)} scraped quotes, {added} unique")
    else:
        print(f"  No scraped_quotes.jsonl found (run scraper first)")

    # Step 4: Scrape online quote sources
    print("\n  --- From online sources ---")
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        wikiquote_quotes = await scrape_wikiquote(client, persona_id)
        added = add_unique(wikiquote_quotes)
        print(f"  Wikiquote: {len(wikiquote_quotes)} found, {added} unique")

    # Summary
    print(f"\n  TOTAL UNIQUE QUOTES: {len(all_quotes)}")

    type_counts: dict[str, int] = {}
    for q in all_quotes:
        st = q["source_type"]
        type_counts[st] = type_counts.get(st, 0) + 1
    for st, count in sorted(type_counts.items()):
        print(f"    {st}: {count}")

    # Save
    output_path = Path(settings.data_dir) / persona_id / "quotes" / "all_quotes.jsonl"
    save_quotes(all_quotes, output_path)


async def extract_all():
    """Extract quotes for all personas."""
    from personas import VALID_PERSONA_IDS

    print("=" * 60)
    print("QUOTE EXTRACTION — ALL PERSONAS")
    print("=" * 60)

    for persona_id in VALID_PERSONA_IDS:
        await extract_for_persona(persona_id)

    # Final summary
    print("\n" + "=" * 60)
    print("EXTRACTION COMPLETE")
    print("=" * 60)

    data_dir = Path(settings.data_dir)
    for pid in VALID_PERSONA_IDS:
        quotes_file = data_dir / pid / "quotes" / "all_quotes.jsonl"
        if quotes_file.exists():
            count = sum(1 for line in open(quotes_file) if line.strip())
            print(f"  {pid}: {count} quotes")
        else:
            print(f"  {pid}: no quotes file")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Romanian Personas Quote Extraction")
    parser.add_argument("--persona", type=str, help="Specific persona ID")
    args = parser.parse_args()

    if args.persona:
        asyncio.run(extract_for_persona(args.persona))
    else:
        asyncio.run(extract_all())
