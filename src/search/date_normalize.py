# owner: pubmed-query
"""Date normalization for PubMed's variable date formats.

PubMed returns dates in several formats across ArticleDate, PubDate,
and MedlineDate elements. This module normalizes them to YYYY-MM-DD
or YYYY-MM strings.
"""

import xml.etree.ElementTree as ET

# Map three-letter month abbreviations to zero-padded numbers.
MONTH_MAP = {
    "jan": "01", "feb": "02", "mar": "03", "apr": "04",
    "may": "05", "jun": "06", "jul": "07", "aug": "08",
    "sep": "09", "oct": "10", "nov": "11", "dec": "12",
}


def _month_to_number(month_str: str) -> str:
    """Convert a month string to a zero-padded number.

    Accepts numeric strings like '3' or '03', or name abbreviations
    like 'Mar' or 'march'. Returns a two-digit string like '03'.
    """
    stripped = month_str.strip()
    # If it's already numeric, just zero-pad it.
    if stripped.isdigit():
        return stripped.zfill(2)
    # Otherwise, look up the first three letters (case-insensitive).
    key = stripped[:3].lower()
    return MONTH_MAP.get(key, "")


def normalize_pub_date(article_elem: ET.Element) -> str:
    """Extract and normalize publication date from a PubmedArticle element.

    Strategy (following PubMed conventions):
    1. Try ArticleDate first — has Year, Month, Day sub-elements.
       Returns YYYY-MM-DD.
    2. Fall back to PubDate — has Year and optionally Month/Day.
       Month may be a name like 'Mar' or a number like '03'.
       Returns YYYY-MM-DD or YYYY-MM depending on available fields.
    3. Fall back to MedlineDate inside PubDate — free-text like
       '2026 Mar-Apr'. Extract the year and the first month.
       Returns YYYY-MM or just the raw text if parsing fails.

    Returns an empty string if no date information is found.
    """
    # --- 1. ArticleDate (electronic publication date) ---
    date_el = article_elem.find(".//ArticleDate")
    if date_el is not None:
        result = _parse_ymd(date_el)
        if result:
            return result

    # --- 2. PubDate with Year/Month/Day sub-elements ---
    pub_date_el = article_elem.find(".//PubDate")
    if pub_date_el is not None:
        result = _parse_ymd(pub_date_el)
        if result:
            return result

        # --- 3. MedlineDate fallback ---
        medline_el = pub_date_el.find("MedlineDate")
        if medline_el is not None and medline_el.text:
            return _parse_medline_date(medline_el.text)

    return ""


def _parse_ymd(date_el: ET.Element) -> str:
    """Parse a date element with Year, Month, Day sub-elements.

    Returns YYYY-MM-DD, YYYY-MM, YYYY, or empty string.
    """
    year_el = date_el.find("Year")
    if year_el is None or not year_el.text:
        return ""

    year = year_el.text.strip()
    month_el = date_el.find("Month")
    if month_el is None or not month_el.text:
        return year

    month = _month_to_number(month_el.text)
    if not month:
        return year

    day_el = date_el.find("Day")
    if day_el is not None and day_el.text and day_el.text.strip().isdigit():
        day = day_el.text.strip().zfill(2)
        return f"{year}-{month}-{day}"

    return f"{year}-{month}"


def _parse_medline_date(text: str) -> str:
    """Parse a MedlineDate string like '2026 Mar-Apr' or '2026 Spring'.

    Extracts the year and the first recognizable month.
    Returns YYYY-MM if a month is found, otherwise just the year portion.
    """
    parts = text.split()
    if not parts:
        return ""

    # The first token that looks like a 4-digit year.
    year = ""
    for part in parts:
        if part.isdigit() and len(part) == 4:
            year = part
            break

    if not year:
        return text  # Can't parse — return raw text as last resort.

    # Look for a month in the remaining tokens.
    for part in parts:
        if part == year:
            continue
        # Handle ranges like 'Mar-Apr' — take the first month.
        token = part.split("-")[0]
        month = _month_to_number(token)
        if month:
            return f"{year}-{month}"

    return year
