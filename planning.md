# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the 40-item mock listings dataset for pieces matching the user's description. Filters by size and max price, then scores each remaining item by keyword overlap against the title, description, style_tags, category, brand, and colors fields. Items scoring zero are dropped. Results are returned sorted by score descending.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): Keywords describing the item the user wants (e.g., "vintage graphic tee").
- `size` (str): Optional size filter. If provided, only matching sizes are returned.
- `max_price` (float): Optional maximum price filter.

**What it returns:**
A list of listing dictionaries sorted by relevance. Each listing contains:
id
title
description
category
style_tags
size
condition
price
colors
brand
platform

**What happens if it fails or returns nothing:**
Returns an empty list. The agent stops the workflow, informs the user that no matching items were found, and suggests broadening the search criteria.

---

### Tool 2: suggest_outfit

**What it does:**
Uses the selected listing and the user's wardrobe to generate one or more outfit ideas. If the user has no wardrobe items saved, it provides general styling suggestions.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): The selected thrift listing returned from search_listings.
- `wardrobe` (dict): The user's wardrobe containing an items list.

**What it returns:**
A string containing one or two complete outfit suggestions that incorporate the selected item.

**What happens if it fails or returns nothing:**
If the wardrobe is empty, the tool generates general styling advice instead of specific combinations. The workflow continues normally.

---

### Tool 3: create_fit_card

**What it does:**
Calls the LLM at temperature 1.0 to generate a 2–4 sentence casual social caption (Instagram/TikTok style). The prompt provides the outfit description, item title, price, and platform, and instructs the model to sound like a real person posting an OOTD — not a brand.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
outfit: str, new_item: dict

**What it returns:**
A short caption suitable for Instagram, TikTok, or other social platforms.

**What happens if it fails or returns nothing:**
Returns a descriptive error message explaining that outfit information is missing. The agent does not crash.

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
run_agent() in agent.py follows a sequential conditional loop with early exit:

1. Initialize session — a fresh dict holding all state for this interaction.
2. Parse query — the Groq LLM extracts description, size, and max_price from the natural language query. Falls back to regex if the LLM is unavailable.
3. Call search_listings — if results are empty, set session["error"] with a helpful message and return immediately. suggest_outfit and create_fit_card are never called with empty input.
4. Select top result — session["selected_item"] = results[0].
5. Call suggest_outfit with the selected item and wardrobe.
6. Call create_fit_card with the outfit suggestion and selected item.
7. Return the completed session.

The loop is not a fixed three-tool sequence — the branch at step 3 means the agent's behavior genuinely differs based on what search_listings returns.

---

## State Management

**How does information from one tool get passed to the next?**
All state lives in a single session dict created by _new_session(). No global variables are used. Each call to run_agent() gets a fresh session, preventing state leakage between queries.

query
Field: the original natural language string the user typed
Set when: initialization, passed into _new_session()
Used by: LLM query parser in step 2

parsed
Field: dict with keys description, size, max_price extracted from the query
Set when: after LLM (or regex fallback) parses the query
Used by: search_listings call in step 3

search_results
Field: list of matching listing dicts returned by search_listings
Set when: after search_listings runs in step 3
Used by: step 3 branch check — if empty, agent exits early

selected_item
Field: the single listing dict chosen as the top result (results[0])
Set when: step 3, only if search_results is non-empty
Used by: suggest_outfit in step 5, create_fit_card in step 6

wardrobe
Field: the user's wardrobe dict with an items list
Set when: initialization, passed into _new_session()
Used by: suggest_outfit in step 5

outfit_suggestion
Field: the string returned by suggest_outfit
Set when: after suggest_outfit runs in step 5
Used by: create_fit_card in step 6

fit_card
Field: the caption string returned by create_fit_card
Set when: after create_fit_card runs in step 6
Used by: returned to UI, displayed in panel 3

error
Field: a human-readable error message string, or None on success
Set when: step 3, if search_results is empty (early exit triggered)
Used by: returned to UI — shown in panel 1, panels 2 & 3 left blank

app.py's handle_query() reads directly from the returned session dict to populate the three output panels.
---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

search_listings: No results
Failure mode: Query + filters produce zero matches.
Agent response: Sets session["error"] to: "No listings found matching '[description]'[in size X][under $Y]. Try broadening your search — remove the size filter, raise your price ceiling, or use different keywords." Returns session immediately. outfit_suggestion and fit_card remain None. The UI shows the error message in panel 1 and leaves panels 2 and 3 blank.


suggest_outfit — Empty wardrobe
Failure mode: wardrobe['items'] is [].
Agent response: Rather than crashing or returning "", the function detects the empty wardrobe and sends a different prompt to the LLM — asking for general styling advice (what types of pieces pair well with the item) instead of referencing specific wardrobe items.


create_fit_card — Empty outfit string
Failure mode: outfit is "" or whitespace-only.
Agent response: Returns the error string: "Cannot create fit card: outfit description is missing. Please ensure suggest_outfit ran successfully first." No exception is raised.

---

## Architecture

```
User query (natural language)
    │
    ▼
run_agent(query, wardrobe)
    │
    ▼
Step 1: _new_session(query, wardrobe)
    │
    ▼
Step 2: LLM Query Parser
    │   Extracts: description (str), size (str|None), max_price (float|None)
    │   → session["parsed"]
    │
    ▼
Step 3: search_listings(description, size, max_price)
    │   → session["search_results"]
    │
    ├── results == [] ──────────────────────────────────────────────────┐
    │       │                                                           │
    │       ▼                                                           │
    │   session["error"] = "No listings found..."                       │
    │   return session  ←────────────────── ERROR PATH EXITS HERE ──────┘
    │
    │ results non-empty
    │   session["selected_item"] = results[0]
    │
    ▼
Step 4: suggest_outfit(selected_item, wardrobe)
    │   → session["outfit_suggestion"]
    │
    │   [Internal branch: wardrobe empty?]
    │   ├── empty → LLM prompt: general styling advice
    │   └── populated → LLM prompt: specific wardrobe combinations
    │
    ▼
Step 5: create_fit_card(outfit_suggestion, selected_item)
    │   → session["fit_card"]
    │
    │   [Internal guard: outfit empty?]
    │   └── empty → return error string (no exception)
    │
    ▼
Return session
    │
    ▼
handle_query() in app.py
    ├── session["error"] set? → return error in panel 1, "" for panels 2 & 3
    └── success? → format selected_item → panel 1
                   session["outfit_suggestion"] → panel 2
                   session["fit_card"] → panel 3
```

---

## AI Tool Plan

**Milestone 3 — Individual tool implementations:**
Tool 1 (search_listings): I will give Claude the Tool 1 spec block above (inputs, return value, failure mode, scoring strategy) and instruct it to implement search_listings() using load_listings() from utils/data_loader.py. I will verify: (a) all three parameters are used, (b) size filtering is case-insensitive, (c) scoring checks title + description + style_tags + category + brand + colors, (d) score-0 items are dropped, (e) the function returns [] not an exception on no match. I will test with 3 queries: one matching multiple items, one matching zero items, and one with a tight price filter.
Tool 2 (suggest_outfit): I will give Claude the Tool 2 spec (inputs, return value, empty wardrobe branch, LLM call pattern) and ask it to implement suggest_outfit() using the Groq client. I will verify: (a) it checks wardrobe['items'] for emptiness, (b) two distinct prompt paths exist, (c) wardrobe items are named specifically in the populated-wardrobe prompt, (d) it never returns "". I will test with both get_example_wardrobe() and get_empty_wardrobe().
Tool 3 (create_fit_card): I will give Claude the Tool 3 spec (style guidelines, temperature note, empty-outfit guard) and ask it to implement create_fit_card(). I will verify: (a) outfit.strip() == "" guard is present, (b) temperature is set to 0.9+, (c) item name, price, and platform appear in the prompt. I will run it 3 times on the same input and confirm outputs differ.

**Milestone 4 — Planning loop and state management:**
I will give Claude the full Architecture diagram above and the Planning Loop + State Management sections, and ask it to implement run_agent() in agent.py. Before accepting the code I will check: (a) _new_session() is called first, (b) the LLM parser extracts description/size/max_price, (c) the search_results == [] branch exits early and does NOT call suggest_outfit, (d) selected_item is set from results[0], (e) outfit and fit_card are stored in the session. I will then test the happy path and the no-results path explicitly.

---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The LLM parser receives the raw query and extracts:
description = "vintage graphic tee"
size = None (no size mentioned)
max_price = 30.0
These are stored in session["parsed"].

**Step 2:**
search_listings:
Called with search_listings("vintage graphic tee", size=None, max_price=30.0).
The function loads all 40 listings, filters to those priced ≤ $30, then scores each by keyword overlap with "vintage graphic tee". Listings like lst_006 ("Graphic Tee — 2003 Tour Bootleg Style", $24, tags: ["graphic tee", "vintage", "grunge", "streetwear", "band tee"]) score highly. lst_033 ("Vintage Band Tee — Faded Grey", $19) also scores well. Results sorted: [lst_006, lst_033, lst_002, ...].
session["search_results"] = [lst_006, lst_033, ...]
session["selected_item"] = lst_006
Returns: A list of full listing dicts sorted by relevance score

**Step 3:**
suggest_outfit:
Called with suggest_outfit(lst_006, example_wardrobe).
The wardrobe has 10 items. The LLM receives a prompt listing the new item ("Graphic Tee — 2003 Tour Bootleg Style, black, $24, size L, grunge/streetwear") and the wardrobe items. It returns something like: "Outfit 1: Pair this boxy black graphic tee with your baggy straight-leg dark wash jeans (w_001) and chunky white sneakers (w_007) — tuck the front slightly for shape. Throw your vintage black denim jacket (w_006) over the top for a 90s layered look. Outfit 2: With your wide-leg khakis (w_002) and black combat boots (w_008), this tee hits more downtown cool than grunge."
session["outfit_suggestion"] = the above string.


create_fit_card:
Called with create_fit_card(outfit_suggestion, lst_006).
The LLM receives the outfit description and item details and generates a caption. Returns something like: "found this faded graphic tee on depop for $24 and it was literally made for my rotation 🖤 wearing it with baggy dark jeans, chunky sneakers, and my denim jacket over top — full 90s moment. vintage finds hitting different rn."
session["fit_card"] = the above string.


**Final output to user:**
Panel 1 (listing): "Graphic Tee — 2003 Tour Bootleg Style | $24.00 | Size: L | Condition: good | Platform: depop | Style: graphic tee, vintage, grunge, streetwear, band tee"
Panel 2 (outfit): The full outfit suggestion from Step 3.
Panel 3 (fit card): The caption from Step 4.
