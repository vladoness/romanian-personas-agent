"""Scrape ro.wikisource.org, ro.wikipedia.org, and quote sites for persona data.

Usage:
  python -m ingest.scraper                        # scrape all personas
  python -m ingest.scraper --persona eminescu     # single persona
  python -m ingest.scraper --works                # works only
  python -m ingest.scraper --profile              # profile (Wikipedia) only
  python -m ingest.scraper --quotes               # quotes only
  python -m ingest.scraper --work-articles        # Wikipedia articles about works
"""

import asyncio
import re
import sys
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from config import settings


# ---------------------------------------------------------------------------
# Shared HTTP helpers
# ---------------------------------------------------------------------------

# Wikimedia requires a descriptive User-Agent per their API policy
HEADERS = {
    "User-Agent": "RomanianPersonasAgent/1.0 (educational-project; contact@example.com)",
}
# Separate headers for non-Wikimedia sites
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
}


async def fetch_page(client: httpx.AsyncClient, url: str) -> str:
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def sanitize_filename(title: str) -> str:
    """Convert title to a safe filename."""
    name = re.sub(r"[^\w\s-]", "", title)
    name = re.sub(r"[\s]+", "-", name.strip())
    return name[:120]


# ---------------------------------------------------------------------------
# Wikisource scraping (literary works)
# ---------------------------------------------------------------------------

# Author page URLs on Romanian Wikisource
WIKISOURCE_AUTHORS = {
    "eminescu": "https://ro.wikisource.org/wiki/Autor:Mihai_Eminescu",
    "caragiale": "https://ro.wikisource.org/wiki/Autor:Ion_Luca_Caragiale",
    "cioran": "https://ro.wikisource.org/wiki/Autor:Emil_Cioran",
    "eliade": "https://ro.wikisource.org/wiki/Autor:Mircea_Eliade",
}

# Known major works to ensure they're captured (fallback if not found via author page)
KNOWN_WORKS = {
    "eminescu": [
        ("Luceafarul", "https://ro.wikisource.org/wiki/Luceaf%C4%83rul"),
        ("Scrisoarea I", "https://ro.wikisource.org/wiki/Scrisoarea_I"),
        ("Scrisoarea II", "https://ro.wikisource.org/wiki/Scrisoarea_II"),
        ("Scrisoarea III", "https://ro.wikisource.org/wiki/Scrisoarea_III"),
        ("Scrisoarea IV", "https://ro.wikisource.org/wiki/Scrisoarea_IV"),
        ("Scrisoarea V", "https://ro.wikisource.org/wiki/Scrisoarea_V"),
        ("Doina", "https://ro.wikisource.org/wiki/Doina_(Eminescu)"),
        ("Floare albastra", "https://ro.wikisource.org/wiki/Floare_albastr%C4%83"),
        ("Sara pe deal", "https://ro.wikisource.org/wiki/%C8%98ara_pe_deal"),
        ("Glossa", "https://ro.wikisource.org/wiki/Gloss%C4%83"),
        ("Mai am un singur dor", "https://ro.wikisource.org/wiki/Mai_am_un_singur_dor"),
        ("Lacul", "https://ro.wikisource.org/wiki/Lacul_(Eminescu)"),
        ("Dintre sute de catarge", "https://ro.wikisource.org/wiki/Dintre_sute_de_catarge"),
        ("Ce te legeni", "https://ro.wikisource.org/wiki/Ce_te_legeni..."),
        ("O mama", "https://ro.wikisource.org/wiki/O,_mam%C4%83..."),
        ("La steaua", "https://ro.wikisource.org/wiki/La_steaua"),
        ("Epigonii", "https://ro.wikisource.org/wiki/Epigonii"),
        ("Imparat si proletar", "https://ro.wikisource.org/wiki/%C3%8Emp%C4%83rat_%C8%99i_proletar"),
        ("Calin file din poveste", "https://ro.wikisource.org/wiki/C%C4%83lin_(file_din_poveste)"),
        ("Mortua est", "https://ro.wikisource.org/wiki/Mortua_est!"),
    ],
    "caragiale": [
        ("O noapte furtunoasa", "https://ro.wikisource.org/wiki/O_noapte_furtunoas%C4%83"),
        ("O scrisoare pierduta", "https://ro.wikisource.org/wiki/O_scrisoare_pierdut%C4%83"),
        ("D-ale carnavalului", "https://ro.wikisource.org/wiki/D-ale_carnavalului"),
        ("Momente si schite", "https://ro.wikisource.org/wiki/Momente_%C8%99i_schi%C8%9Be"),
    ],
    "cioran": [
        ("Pe culmile disperarii", "https://ro.wikisource.org/wiki/Pe_culmile_disper%C4%83rii"),
        ("Cartea amagirilor", "https://ro.wikisource.org/wiki/Cartea_am%C4%83girilor"),
        ("Lacrimi si sfinti", "https://ro.wikisource.org/wiki/Lacrimi_%C8%99i_sfin%C8%9Bi"),
    ],
    "eliade": [],
    "bratianu": [],
}


async def get_wikisource_work_urls(client: httpx.AsyncClient, author_url: str) -> list[tuple[str, str]]:
    """Scrape a Wikisource author page to find all linked works."""
    try:
        html = await fetch_page(client, author_url)
        soup = BeautifulSoup(html, "html.parser")

        works = []
        # Find all links within the main content area
        content = soup.find("div", {"class": "mw-parser-output"})
        if not content:
            return []

        for link in content.find_all("a", href=True):
            href = link["href"]
            title = link.get_text(strip=True)

            # Filter: internal wiki links, not author/category/special pages
            if not href.startswith("/wiki/"):
                continue
            if any(x in href for x in ["Autor:", "Categorie:", "Special:", "Ajutor:", "Wikisource:"]):
                continue
            if not title or len(title) < 2:
                continue

            full_url = f"https://ro.wikisource.org{href}"
            works.append((title, full_url))

        # Deduplicate by URL
        seen = set()
        unique = []
        for title, url in works:
            if url not in seen:
                seen.add(url)
                unique.append((title, url))

        return unique
    except Exception as e:
        print(f"  Error scraping author page {author_url}: {e}")
        return []


async def scrape_wikisource_text(client: httpx.AsyncClient, url: str) -> str | None:
    """Extract clean text from a Wikisource page using MediaWiki parse API."""
    try:
        # Extract page title from URL
        if "/wiki/" in url:
            page_title = url.split("/wiki/")[-1]
        else:
            return None

        # Use parse API to get wikitext, then clean markup
        api_url = "https://ro.wikisource.org/w/api.php"
        params = {
            "action": "parse",
            "page": page_title,
            "prop": "wikitext",
            "format": "json",
        }

        resp = await client.get(api_url, params=params, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()

        if "parse" not in data:
            return None

        wikitext = data["parse"]["wikitext"]["*"]

        # Check if this is a disambiguation or redirect page
        if "{{dezambig}}" in wikitext.lower() or "#redirect" in wikitext.lower():
            return None

        # Strip wikitext markup for clean text
        clean = _clean_wikitext(wikitext)

        if clean and len(clean) > 50:
            return clean

        return None
    except Exception as e:
        print(f"    Error fetching Wikisource text from {url}: {e}")
        return None


def _clean_wikitext(text: str) -> str:
    """Remove wikitext markup, keeping clean readable text."""
    # Remove templates {{...}}
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # Remove nested templates
    text = re.sub(r"\{\{[^}]*\}\}", "", text)
    # Convert wikilinks [[target|display]] or [[target]] to display text
    text = re.sub(r"\[\[([^|\]]*\|)?([^\]]*)\]\]", r"\2", text)
    # Remove bold/italic markup
    text = re.sub(r"'{2,3}", "", text)
    # Remove <ref> tags and content
    text = re.sub(r"<ref[^>]*>.*?</ref>", "", text, flags=re.DOTALL)
    text = re.sub(r"<ref[^/]*/?>", "", text)
    # Remove HTML tags but keep content
    text = re.sub(r"</?(?:poem|center|div|span|small|big|nowiki|br\s*/?)>", "", text)
    # Remove category links
    text = re.sub(r"\[\[Categorie:[^\]]*\]\]", "", text)
    # Clean up whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def scrape_works_for_persona(client: httpx.AsyncClient, persona_id: str):
    """Scrape all available literary works for a persona from Wikisource."""
    works_dir = Path(settings.data_dir) / persona_id / "works"
    works_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Scraping works for {persona_id} ---")

    # Discover works from author page
    all_works = []
    if persona_id in WIKISOURCE_AUTHORS:
        print(f"  Discovering works from {WIKISOURCE_AUTHORS[persona_id]}")
        discovered = await get_wikisource_work_urls(client, WIKISOURCE_AUTHORS[persona_id])
        all_works.extend(discovered)
        print(f"  Discovered {len(discovered)} works from author page")

    # Merge known works
    known_urls = {url for _, url in all_works}
    for title, url in KNOWN_WORKS.get(persona_id, []):
        if url not in known_urls:
            all_works.append((title, url))
    print(f"  Total works to scrape: {len(all_works)}")

    # Scrape each work
    scraped = 0
    skipped = 0
    for title, url in all_works:
        filename = sanitize_filename(title) + ".md"
        dest = works_dir / filename

        if dest.exists():
            skipped += 1
            continue

        text = await scrape_wikisource_text(client, url)
        if text:
            md_content = f"# {title}\n\nSursa: {url}\n\n{text}"
            dest.write_text(md_content, encoding="utf-8")
            scraped += 1
            await asyncio.sleep(1.0)  # Rate limit per Wikimedia policy
        else:
            print(f"    Skipped (no content): {title}")

    print(f"  Scraped: {scraped}, Skipped (existing): {skipped}, Failed: {len(all_works) - scraped - skipped}")


# ---------------------------------------------------------------------------
# Wikipedia profile scraping
# ---------------------------------------------------------------------------

WIKIPEDIA_PROFILE_URLS = {
    "eminescu": [
        ("ro", "https://ro.wikipedia.org/wiki/Mihai_Eminescu"),
    ],
    "bratianu": [
        ("ro", "https://ro.wikipedia.org/wiki/Ion_C._Br%C4%83tianu"),
    ],
    "caragiale": [
        ("ro", "https://ro.wikipedia.org/wiki/Ion_Luca_Caragiale"),
    ],
    "eliade": [
        ("ro", "https://ro.wikipedia.org/wiki/Mircea_Eliade"),
        ("en", "https://en.wikipedia.org/wiki/Mircea_Eliade"),
    ],
    "cioran": [
        ("ro", "https://ro.wikipedia.org/wiki/Emil_Cioran"),
        ("en", "https://en.wikipedia.org/wiki/Emil_Cioran"),
    ],
}


async def scrape_wikipedia_profile(client: httpx.AsyncClient, url: str, lang: str) -> str | None:
    """Extract clean text from a Wikipedia article via MediaWiki API."""
    try:
        from urllib.parse import unquote

        # Use MediaWiki API for cleaner extraction
        if "wikipedia.org/wiki/" in url:
            page_title = unquote(url.split("/wiki/")[-1])
            wiki_domain = url.split("/wiki/")[0]
            api_url = f"{wiki_domain}/w/api.php"
            params = {
                "action": "query",
                "titles": page_title,
                "prop": "extracts",
                "explaintext": True,
                "format": "json",
            }
            resp = await client.get(api_url, params=params, follow_redirects=True)
            resp.raise_for_status()
            data = resp.json()

            pages = data.get("query", {}).get("pages", {})
            for page_id, page_data in pages.items():
                if page_id == "-1":
                    return None
                text = page_data.get("extract", "")
                if text and len(text) > 100:
                    return text

        # Fallback to trafilatura
        import trafilatura

        html = await fetch_page(client, url)
        text = trafilatura.extract(html, include_comments=False, include_tables=True)
        return text
    except Exception as e:
        print(f"  Error extracting Wikipedia article {url}: {e}")
        return None


async def scrape_profile_for_persona(client: httpx.AsyncClient, persona_id: str):
    """Scrape Wikipedia profiles for a persona."""
    profile_dir = Path(settings.data_dir) / persona_id / "profile"
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Scraping Wikipedia profiles for {persona_id} ---")

    urls = WIKIPEDIA_PROFILE_URLS.get(persona_id, [])
    if not urls:
        print(f"  No Wikipedia URLs configured for {persona_id}")
        return

    for lang, url in urls:
        filename = f"wikipedia_{lang}.md"
        dest = profile_dir / filename

        if dest.exists():
            print(f"  Already exists: {filename}")
            continue

        print(f"  Scraping: {url}")
        text = await scrape_wikipedia_profile(client, url, lang)
        if text:
            md_content = f"# Wikipedia ({lang.upper()}) — {persona_id.title()}\n\nSursa: {url}\n\n{text}"
            dest.write_text(md_content, encoding="utf-8")
            print(f"  Saved: {filename} ({len(text)} chars)")
        else:
            print(f"  Failed to extract content")

        await asyncio.sleep(1.0)  # Rate limit per Wikimedia policy


# ---------------------------------------------------------------------------
# Quote scraping from aggregator sites
# ---------------------------------------------------------------------------

WIKIQUOTE_URLS = {
    "eminescu": "https://ro.wikiquote.org/wiki/Mihai_Eminescu",
    "bratianu": "https://ro.wikiquote.org/wiki/Ion_C._Br%C4%83tianu",
    "caragiale": "https://ro.wikiquote.org/wiki/Ion_Luca_Caragiale",
    "eliade": [
        "https://ro.wikiquote.org/wiki/Mircea_Eliade",
        "https://en.wikiquote.org/wiki/Mircea_Eliade",
    ],
    "cioran": [
        "https://ro.wikiquote.org/wiki/Emil_Cioran",
        "https://en.wikiquote.org/wiki/Emil_Cioran",
    ],
}

GOODREADS_QUOTE_URLS = {
    "eminescu": "https://www.goodreads.com/author/quotes/276048.Mihai_Eminescu",
    "bratianu": None,  # Not on Goodreads
    "caragiale": "https://www.goodreads.com/author/quotes/319444.Ion_Luca_Caragiale",
    "eliade": "https://www.goodreads.com/author/quotes/33244.Mircea_Eliade",
    "cioran": "https://www.goodreads.com/author/quotes/8463.Emil_M_Cioran",
}

ROMANIAN_QUOTE_SITES = {
    "citate-celebre.ro": "https://www.citate-celebre.ro/citate-de/{author}/",
    "citatepedia.ro": "https://www.citatepedia.ro/autor/{author}/",
}


async def scrape_wikiquote_quotes(client: httpx.AsyncClient, url: str, lang: str) -> list[str]:
    """Extract quotes from a Wikiquote page."""
    try:
        html = await fetch_page(client, url)
        soup = BeautifulSoup(html, "html.parser")

        quotes = []
        # Wikiquote stores quotes in <li> tags within content div
        content = soup.find("div", {"class": "mw-parser-output"})
        if not content:
            return []

        # Find all <ul> elements (quote lists)
        for ul in content.find_all("ul"):
            for li in ul.find_all("li", recursive=False):
                # Extract text, clean up references and wiki markup
                text = li.get_text(strip=True)
                # Remove citation markers like [1], [2]
                text = re.sub(r"\[\d+\]", "", text)
                # Remove parenthetical source info at end
                text = re.sub(r"\s*\([^)]*\)\s*$", "", text)
                text = text.strip()

                if text and len(text) > 20 and len(text) < 800:
                    quotes.append(text)

        return quotes
    except Exception as e:
        print(f"    Error scraping Wikiquote {url}: {e}")
        return []


async def scrape_goodreads_quotes(client: httpx.AsyncClient, url: str) -> list[str]:
    """Extract quotes from a Goodreads author quotes page."""
    try:
        # Use browser headers for Goodreads
        resp = await client.get(url, headers=BROWSER_HEADERS, follow_redirects=True)
        resp.raise_for_status()
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        quotes = []
        # Goodreads quotes are in div.quoteText
        for quote_div in soup.find_all("div", {"class": "quoteText"}):
            text = quote_div.get_text(strip=True)
            # Remove the "―Author Name" attribution
            text = re.sub(r"―[^―]*$", "", text)
            # Remove "tags:" section
            text = re.sub(r"tags:.*$", "", text, flags=re.IGNORECASE)
            text = text.strip()

            # Clean up quotes - remove opening/closing quotes added by Goodreads
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1].strip()
            if text.startswith('"') or text.startswith('\u201c'):
                text = text[1:].strip()
            if text.endswith('"') or text.endswith('\u201d'):
                text = text[:-1].strip()

            if text and len(text) > 20 and len(text) < 800:
                quotes.append(text)

        return quotes
    except Exception as e:
        print(f"    Error scraping Goodreads {url}: {e}")
        return []


async def scrape_quotes_for_persona(client: httpx.AsyncClient, persona_id: str):
    """Scrape quotes from multiple online sources."""
    import json

    quotes_dir = Path(settings.data_dir) / persona_id / "quotes"
    quotes_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Scraping quotes for {persona_id} ---")

    all_quotes = set()  # Use set to deduplicate

    # 1. Wikiquote
    wikiquote_urls = WIKIQUOTE_URLS.get(persona_id, [])
    if isinstance(wikiquote_urls, str):
        wikiquote_urls = [wikiquote_urls]

    for url in wikiquote_urls:
        lang = "ro" if "ro.wikiquote" in url else "en"
        print(f"  Scraping Wikiquote ({lang}): {url}")
        quotes = await scrape_wikiquote_quotes(client, url, lang)
        print(f"    Found {len(quotes)} quotes")
        all_quotes.update(quotes)
        await asyncio.sleep(1.0)

    # 2. Goodreads
    goodreads_url = GOODREADS_QUOTE_URLS.get(persona_id)
    if goodreads_url:
        print(f"  Scraping Goodreads: {goodreads_url}")
        quotes = await scrape_goodreads_quotes(client, goodreads_url)
        print(f"    Found {len(quotes)} quotes")
        all_quotes.update(quotes)
        await asyncio.sleep(2.0)

    # Save to JSONL
    if all_quotes:
        output_file = quotes_dir / "scraped_quotes.jsonl"
        with open(output_file, "w", encoding="utf-8") as f:
            for quote in sorted(all_quotes):
                entry = {
                    "text": quote,
                    "source_file": "online_aggregators",
                    "source_type": "scraped_quote",
                    "char_count": len(quote),
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print(f"  Saved {len(all_quotes)} unique quotes to {output_file}")
    else:
        print(f"  No quotes found for {persona_id}")


# ---------------------------------------------------------------------------
# Wikipedia articles about works (for personas without Wikisource texts)
# ---------------------------------------------------------------------------

WORK_ARTICLE_URLS = {
    "bratianu": [
        # Political documents and speeches about his work
        ("Constituția României (1866)", "https://ro.wikipedia.org/wiki/Constitu%C8%9Bia_Rom%C3%A2niei_(1866)"),
        ("Războiul de Independență al României", "https://ro.wikipedia.org/wiki/R%C4%83zboiul_de_Independen%C8%9B%C4%83_al_Rom%C3%A2niei"),
        ("Partidul Național Liberal (România)", "https://ro.wikipedia.org/wiki/Partidul_Na%C8%9Bional_Liberal_(Rom%C3%A2nia)"),
    ],
    "eliade": [
        ("Maitreyi (roman)", "https://ro.wikipedia.org/wiki/Maitreyi_(roman)"),
        ("Nunta în cer", "https://ro.wikipedia.org/wiki/Nunta_%C3%AEn_cer"),
        ("Noaptea de Sânziene", "https://ro.wikipedia.org/wiki/Noaptea_de_S%C3%A2nziene"),
        ("Sacrul și profanul", "https://ro.wikipedia.org/wiki/Sacrul_%C8%99i_profanul"),
        ("Mitul eternei reîntoarceri", "https://ro.wikipedia.org/wiki/Mitul_eternei_re%C3%AEntoarceri"),
        ("Hierofanie", "https://ro.wikipedia.org/wiki/Hierofanie"),
        ("Axis mundi", "https://en.wikipedia.org/wiki/Axis_mundi"),
        ("Mircea Eliade (English)", "https://en.wikipedia.org/wiki/Mircea_Eliade"),
        ("The Sacred and the Profane", "https://en.wikipedia.org/wiki/The_Sacred_and_the_Profane"),
        ("Shamanism: Archaic Techniques of Ecstasy", "https://en.wikipedia.org/wiki/Shamanism:_Archaic_Techniques_of_Ecstasy"),
    ],
    "cioran": [
        ("Pe culmile disperării", "https://ro.wikipedia.org/wiki/Pe_culmile_disper%C4%83rii"),
        ("Cartea amăgirilor", "https://ro.wikipedia.org/wiki/Cartea_am%C4%83girilor"),
        ("Schimbarea la față a României", "https://ro.wikipedia.org/wiki/Schimbarea_la_fa%C8%9B%C4%83_a_Rom%C3%A2niei"),
        ("Silogismele amărăciunii", "https://ro.wikipedia.org/wiki/Silogismele_am%C4%83r%C4%83ciunii"),
        ("Ispita de a exista", "https://ro.wikipedia.org/wiki/Ispita_de_a_exista"),
        ("Despre neajunsul de a te fi născut", "https://ro.wikipedia.org/wiki/Despre_neajunsul_de_a_te_fi_n%C4%83scut"),
        ("Emil Cioran (English)", "https://en.wikipedia.org/wiki/Emil_Cioran"),
        ("The Trouble with Being Born", "https://en.wikipedia.org/wiki/The_Trouble_with_Being_Born"),
    ],
}


async def scrape_work_articles_for_persona(client: httpx.AsyncClient, persona_id: str):
    """Scrape Wikipedia articles about a persona's works (as proxy content when texts unavailable)."""
    works_dir = Path(settings.data_dir) / persona_id / "works"
    works_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n--- Scraping Wikipedia articles about {persona_id}'s works ---")

    articles = WORK_ARTICLE_URLS.get(persona_id, [])
    if not articles:
        print(f"  No work articles configured for {persona_id}")
        return

    scraped = 0
    for title, url in articles:
        filename = sanitize_filename(title) + "_wikipedia.md"
        dest = works_dir / filename

        if dest.exists():
            print(f"  Already exists: {filename}")
            continue

        print(f"  Scraping: {title}")
        lang = "ro" if "ro.wikipedia" in url else "en"
        text = await scrape_wikipedia_profile(client, url, lang)

        if text:
            md_content = f"# {title} (Wikipedia)\n\nSursa: {url}\n\n{text}"
            dest.write_text(md_content, encoding="utf-8")
            scraped += 1
            print(f"    Saved: {filename} ({len(text)} chars)")
        else:
            print(f"    Failed to extract content")

        await asyncio.sleep(1.0)

    print(f"  Scraped {scraped} work articles for {persona_id}")


# ---------------------------------------------------------------------------
# Bratianu special handling (archive.org, manual sources)
# ---------------------------------------------------------------------------

BRATIANU_SPEECH_URLS = [
    # Archive.org digitized compilations (OCR text)
    ("Discurs 1866 - Adunarea Constituanta", None),
    # These will need manual addition — placeholder for archive.org integration
]


async def scrape_bratianu_special(client: httpx.AsyncClient):
    """Special scraping for Bratianu — limited online sources need supplementation."""
    works_dir = Path(settings.data_dir) / "bratianu" / "works"
    works_dir.mkdir(parents=True, exist_ok=True)

    print("\n--- Bratianu: limited online sources ---")
    print("  NOTE: Bratianu's works are not available on Wikisource.")
    print("  Place manually curated speeches and texts in:")
    print(f"    {works_dir}")
    print("  Recommended sources:")
    print("    - archive.org: 'Acte si Cuvintari' compilations")
    print("    - dacoromanica.ro: digitized 19th century documents")
    print("    - Manual transcriptions from historical texts")


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

async def scrape_persona(
    persona_id: str,
    works: bool = True,
    profile: bool = True,
    quotes: bool = True,
    work_articles: bool = True,
):
    """Scrape all data sources for a single persona."""
    async with httpx.AsyncClient(timeout=30.0, headers=HEADERS) as client:
        if works:
            if persona_id == "bratianu":
                await scrape_bratianu_special(client)
            else:
                await scrape_works_for_persona(client, persona_id)

        if profile:
            await scrape_profile_for_persona(client, persona_id)

        if quotes:
            await scrape_quotes_for_persona(client, persona_id)

        if work_articles and persona_id in WORK_ARTICLE_URLS:
            await scrape_work_articles_for_persona(client, persona_id)


async def scrape_all(
    works: bool = True,
    profile: bool = True,
    quotes: bool = True,
    work_articles: bool = True,
):
    """Scrape data for all personas."""
    from personas import VALID_PERSONA_IDS

    print("=" * 60)
    print("SCRAPING ALL PERSONAS")
    print("=" * 60)

    for persona_id in VALID_PERSONA_IDS:
        await scrape_persona(persona_id, works=works, profile=profile, quotes=quotes, work_articles=work_articles)

    print("\n" + "=" * 60)
    print("SCRAPING COMPLETE")
    print("=" * 60)

    # Summary
    data_dir = Path(settings.data_dir)
    for pid in VALID_PERSONA_IDS:
        works_count = len(list((data_dir / pid / "works").glob("*.md"))) if (data_dir / pid / "works").exists() else 0
        profile_count = len(list((data_dir / pid / "profile").glob("*.md"))) if (data_dir / pid / "profile").exists() else 0
        quotes_jsonl = list((data_dir / pid / "quotes").glob("*.jsonl")) if (data_dir / pid / "quotes").exists() else []
        quotes_count = sum(1 for f in quotes_jsonl for _ in open(f))
        print(f"  {pid}: {works_count} works, {profile_count} profiles, {quotes_count} quotes")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Romanian Personas Scraper")
    parser.add_argument("--persona", type=str, help="Specific persona ID to scrape")
    parser.add_argument("--works", action="store_true", help="Scrape works only")
    parser.add_argument("--profile", action="store_true", help="Scrape profiles only")
    parser.add_argument("--quotes", action="store_true", help="Scrape quotes only")
    parser.add_argument("--work-articles", action="store_true", help="Scrape Wikipedia work articles only")
    args = parser.parse_args()

    # If no specific flags, do everything
    all_flags = not (args.works or args.profile or args.quotes or args.work_articles)
    do_works = args.works or all_flags
    do_profile = args.profile or all_flags
    do_quotes = args.quotes or all_flags
    do_work_articles = args.work_articles or all_flags

    if args.persona:
        asyncio.run(
            scrape_persona(
                args.persona,
                works=do_works,
                profile=do_profile,
                quotes=do_quotes,
                work_articles=do_work_articles,
            )
        )
    else:
        asyncio.run(
            scrape_all(
                works=do_works,
                profile=do_profile,
                quotes=do_quotes,
                work_articles=do_work_articles,
            )
        )
