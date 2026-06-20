"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    try:
        listings = load_listings()
    except Exception:
        return []

    # Step 1: Filter by max_price
    if max_price is not None:
        listings = [item for item in listings if item["price"] <= max_price]

    # Step 2: Filter by size (case-insensitive substring match in both directions)
    if size is not None:
        size_lower = size.lower()
        filtered = []
        for item in listings:
            item_size = (item.get("size") or "").lower()
            # Match if either contains the other (handles "M" in "S/M", "W30" in "W30 L30", etc.)
            if size_lower in item_size or item_size in size_lower:
                filtered.append(item)
        listings = filtered

    # Step 3: Score each listing by keyword overlap with description
    keywords = set(description.lower().split())
    stopwords = {"a", "an", "the", "for", "in", "of", "and", "or", "i", "my", "me"}
    keywords -= stopwords

    def score_listing(item: dict) -> int:
        searchable_parts = [
            item.get("title", ""),
            item.get("description", ""),
            item.get("category", ""),
            item.get("brand", "") or "",
            " ".join(item.get("style_tags", [])),
            " ".join(item.get("colors", [])),
        ]
        searchable = " ".join(searchable_parts).lower()

        score = 0
        for kw in keywords:
            if kw in searchable:
                score += 1
                # Bonus: keyword in title or style_tags (most relevant fields)
                if kw in item.get("title", "").lower():
                    score += 2
                if any(kw in tag.lower() for tag in item.get("style_tags", [])):
                    score += 1
        return score

    # Step 4: Score all remaining listings and drop score-0 items
    scored = [(item, score_listing(item)) for item in listings]
    scored = [(item, s) for item, s in scored if s > 0]

    # Step 5: Sort by score descending
    scored.sort(key=lambda x: x[1], reverse=True)

    return [item for item, _ in scored]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    try:
        client = _get_groq_client()
    except ValueError as e:
        return f"Could not connect to AI service: {e}"

    item_summary = (
        f"Item: {new_item.get('title', 'Unknown item')}\n"
        f"Category: {new_item.get('category', 'unknown')}\n"
        f"Colors: {', '.join(new_item.get('colors', []))}\n"
        f"Style tags: {', '.join(new_item.get('style_tags', []))}\n"
        f"Condition: {new_item.get('condition', 'unknown')}\n"
        f"Price: ${new_item.get('price', 0):.2f}\n"
        f"Description: {new_item.get('description', '')}"
    )

    wardrobe_items = wardrobe.get("items", [])

    # Step 1: Check whether wardrobe is empty
    if not wardrobe_items:
        # Step 2: Empty wardrobe — general styling advice
        prompt = (
            f"A thrifter just found this secondhand item:\n\n{item_summary}\n\n"
            "They don't have a wardrobe on file yet. Give them 1–2 specific outfit ideas "
            "based on the item's style, colors, and vibe — describe what types of bottoms, "
            "shoes, and accessories would work well. Be specific about colors and silhouettes. "
            "Keep your tone casual and helpful, like a stylish friend texting advice. "
            "2–4 sentences total."
        )
    else:
        # Step 3: Populated wardrobe — suggest specific combinations
        wardrobe_lines = []
        for w_item in wardrobe_items:
            line = (
                f"- {w_item.get('name', 'Unknown')} "
                f"({w_item.get('category', '?')}, "
                f"colors: {', '.join(w_item.get('colors', []))})"
            )
            if w_item.get("notes"):
                line += f" — {w_item['notes']}"
            wardrobe_lines.append(line)
        wardrobe_text = "\n".join(wardrobe_lines)

        prompt = (
            f"A thrifter is considering buying this secondhand item:\n\n{item_summary}\n\n"
            f"Here's what they already own:\n{wardrobe_text}\n\n"
            "Suggest 1–2 complete outfit combinations using the new item and specific pieces "
            "from their wardrobe (refer to wardrobe items by name). For each outfit, describe "
            "the full look: top, bottom, shoes, and optionally an accessory. Note any styling "
            "tips (tucking, layering, rolling sleeves, etc.). Keep the tone casual and specific — "
            "like a stylish friend who knows their closet. 3–6 sentences total."
        )

    # Step 4: Call the LLM and return the response
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.7,
        )
        result = response.choices[0].message.content.strip()
        return result if result else _fallback_outfit_advice(new_item)
    except Exception:
        return _fallback_outfit_advice(new_item)


def _fallback_outfit_advice(new_item: dict) -> str:
    """Fallback styling advice when the LLM call fails."""
    category = new_item.get("category", "item")
    colors = ", ".join(new_item.get("colors", ["neutral tones"]))
    return (
        f"Couldn't generate outfit suggestions right now. "
        f"This {category} in {colors} would pair well with neutral basics — "
        "try dark jeans or simple trousers with clean sneakers or boots."
    )


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    # Step 1: Guard against empty or whitespace-only outfit
    if not outfit or not outfit.strip():
        return (
            "Cannot create fit card: outfit description is missing. "
            "Please ensure suggest_outfit ran successfully first."
        )

    title = new_item.get("title", "this thrifted find")
    price = new_item.get("price", 0)
    platform = new_item.get("platform", "a thrift app")
    style_tags = new_item.get("style_tags", [])
    vibe_hint = ", ".join(style_tags[:3]) if style_tags else "vintage vibes"

    # Step 2: Build the prompt
    prompt = (
        f"Write a casual Instagram/TikTok OOTD caption for this thrifted outfit.\n\n"
        f"The thrifted item: {title} — found on {platform} for ${price:.2f}\n"
        f"Style vibe: {vibe_hint}\n"
        f"The outfit: {outfit}\n\n"
        "Rules for the caption:\n"
        "- 2–4 sentences, very casual tone (like a real person posting, not a brand)\n"
        "- Mention the item name naturally once, the price once, and the platform once\n"
        "- Capture the specific vibe of the outfit (not generic compliments)\n"
        "- End with 1–2 relevant emojis\n"
        "- Do NOT use hashtags\n"
        "- Sound authentic and a little understated — thrift-cool energy\n"
        "Write only the caption text, nothing else."
    )

    # Step 3: Call the LLM and return the response
    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=1.0,
        )
        result = response.choices[0].message.content.strip()
        return result if result else "Fit card generation failed — try again."
    except Exception:
        return "Fit card generation failed. Try again — couldn't reach the AI service."