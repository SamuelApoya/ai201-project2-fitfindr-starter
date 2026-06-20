# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── tests/
│   ├── __init__.py
│   └── test_tools.py          # Pytest tests for each tool
├── agent.py                   # Planning loop — orchestrates the three tools
├── app.py                     # Gradio UI — run this to launch the app
├── tools.py                   # Three required tools: search, outfit, fit card
├── planning.md                # Planning doc — filled out before implementation
├── README.md                  # This file
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## Running the App

```bash
python3 app.py
```

Then open the URL shown in your terminal (usually `http://localhost:7860`).

## Running the Tests

```bash
python3 -m pytest tests/
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Tool Inventory

### `search_listings(description: str, size: str | None, max_price: float | None) → list[dict]`

Searches the 40-item mock listings dataset for pieces matching the user's description. Filters by size (case-insensitive substring match) and max price, then scores each remaining item by keyword overlap against the title, description, style_tags, category, brand, and colors fields. Items scoring zero are dropped. Results are returned sorted by score descending.

**Returns:** A list of listing dicts sorted by relevance. Returns `[]` on no match — never raises.

---

### `suggest_outfit(new_item: dict, wardrobe: dict) → str`

Calls Groq's `llama-3.3-70b-versatile` to generate 1–2 complete outfit combinations. If the wardrobe has items, the prompt names specific wardrobe pieces and asks the LLM to combine them with the new find. If the wardrobe is empty, the prompt asks for general styling advice based on the item's style tags and color palette.

**Returns:** A non-empty string with outfit suggestions. Falls back to a hardcoded advice string if the LLM call fails.

---

### `create_fit_card(outfit: str, new_item: dict) → str`

Calls the LLM at temperature 1.0 to generate a 2–4 sentence casual social caption (Instagram/TikTok style). The prompt provides the outfit description, item title, price, and platform, and instructs the model to sound like a real person posting an OOTD — not a brand.

**Returns:** A caption string. Returns a descriptive error string (not an exception) if `outfit` is empty or the LLM fails.

---

## How the Planning Loop Works

`run_agent()` in `agent.py` follows a sequential conditional loop with early exit:

1. Initialize session dict
2. LLM parses the query into `description`, `size`, and `max_price`
3. Call `search_listings` — if results are empty, set `session["error"]` and return immediately. `suggest_outfit` and `create_fit_card` are never called with empty input.
4. Set `session["selected_item"] = results[0]`
5. Call `suggest_outfit` with the selected item and wardrobe
6. Call `create_fit_card` with the outfit suggestion and selected item
7. Return the completed session

## State Management

All state lives in a single `session` dict created by `_new_session()`. No global variables are used. Each call to `run_agent()` gets a fresh session, preventing state leakage between queries.

`query`
Field: the original natural language string the user typed
Set when: initialization, passed into `_new_session()`
Used by: LLM query parser in step 2

`parsed`
Field: dict with keys `description`, `size`, `max_price` extracted from the query
Set when: after LLM (or regex fallback) parses the query
Used by: `search_listings` call in step 3

`search_results`
Field: list of matching listing dicts returned by `search_listings`
Set when: after `search_listings` runs in step 3
Used by: step 3 branch check — if empty, agent exits early

`selected_item`
Field: the single listing dict chosen as the top result (`results[0]`)
Set when: step 3, only if `search_results` is non-empty
Used by: `suggest_outfit` in step 5, `create_fit_card` in step 6

`wardrobe`
Field: the user's wardrobe dict with an `items` list
Set when: initialization, passed into `_new_session()`
Used by: `suggest_outfit` in step 5

`outfit_suggestion`
Field: the string returned by `suggest_outfit`
Set when: after `suggest_outfit` runs in step 5
Used by: `create_fit_card` in step 6

`fit_card`
Field: the caption string returned by `create_fit_card`
Set when: after `create_fit_card` runs in step 6
Used by: returned to UI, displayed in panel 3

`error`
Field: a human-readable error message string, or `None` on success
Set when: step 3, if `search_results` is empty (early exit triggered)
Used by: returned to UI — shown in panel 1, panels 2 & 3 left blank

## Error Handling

### `search_listings` — No results
**Failure mode:** Query + filters produce zero matches.
**Agent response:** Sets `session["error"]` to: *"No listings found matching '[description]'[in size X][under $Y]. Try broadening your search — remove the size filter, raise your price ceiling, or use different keywords."* Returns session immediately. `outfit_suggestion` and `fit_card` remain `None`.

**Tested with:**
```bash
python3 -c "from tools import search_listings; print(search_listings('designer ballgown', size='XXS', max_price=5))"
# Output: []
```

### `suggest_outfit` — Empty wardrobe
**Failure mode:** `wardrobe['items']` is `[]`.
**Agent response:** Detects the empty wardrobe and sends a different prompt to the LLM — asking for general styling advice instead of referencing specific wardrobe items. Returns a non-empty string. Never crashes.

**Tested with:**
```bash
python3 -c "
from tools import search_listings, suggest_outfit
from utils.data_loader import get_empty_wardrobe
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(suggest_outfit(results[0], get_empty_wardrobe()))
"
# Output: general styling advice string
```

### `create_fit_card` — Empty outfit string
**Failure mode:** `outfit` is `""` or whitespace-only.
**Agent response:** Returns the error string: *"Cannot create fit card: outfit description is missing. Please ensure suggest_outfit ran successfully first."* No exception is raised.

**Tested with:**
```bash
python3 -c "
from tools import search_listings, create_fit_card
results = search_listings('vintage graphic tee', size=None, max_price=50)
print(create_fit_card('', results[0]))
"
# Output: "Cannot create fit card: outfit description is missing..."
```

## Spec Reflection

**One way the spec helped:** Designing the planning loop in `planning.md` before writing code made it obvious that `search_listings` needed to be a gate — if it returns nothing, there's nothing to pass into the LLM tools. Writing that branch in plain English first meant the code just translated the spec directly, with no ambiguity about what to do on empty results.

**One way implementation diverged:** The spec described a simple keyword-scoring approach for `search_listings`. In practice, matching "M" as a size against "S/M" or "One Size / Oversized" required bidirectional substring matching, which wasn't anticipated in the original spec. This also meant very broad size filters like "M" can match "S/M" items, which is actually the right behavior for thrift shopping but wasn't explicitly called out.

## AI Usage

**Instance 1 — `search_listings` implementation:**
Input to Claude: The Tool 1 spec block from `planning.md` (exact parameters, return value description, failure mode) plus the `load_listings()` function signature from `data_loader.py`. Asked Claude to implement the scoring logic using keyword overlap.
What Claude produced: A working function that filtered by price and size and scored by keyword matching. What I revised: The size matching used `==` instead of substring matching, which would have missed "S/M" when searching "M". I changed it to bidirectional `in` checks and added stopword stripping to improve description keyword quality.

**Instance 2 — `agent.py` planning loop:**
Input to Claude: The full Architecture ASCII diagram from `planning.md` and the Planning Loop section describing exact branch conditions. Asked it to implement `run_agent()` following the numbered steps.
What Claude produced: A loop that called all three tools unconditionally on the first pass — the early exit on empty results wasn't implemented. I revised it to add the `if not results:` branch with `return session` and verified by running the no-results test case manually before trusting it.

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python3 utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.
