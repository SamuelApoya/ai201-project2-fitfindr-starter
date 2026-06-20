"""
tests/test_tools.py

Pytest tests for each FitFindr tool, covering happy paths and failure modes.

Run with:
    pytest tests/
"""

import sys
import os

# Make sure tools.py is importable from the project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools import search_listings, suggest_outfit, create_fit_card


# ─────────────────────────────────────────────────
# Tool 1: search_listings
# ─────────────────────────────────────────────────

class TestSearchListings:

    def test_search_returns_results(self):
        """Happy path: description that should match several listings."""
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert isinstance(results, list)
        assert len(results) > 0

    def test_search_empty_results(self):
        """No-match path: should return [] not raise an exception."""
        results = search_listings("designer ballgown", size="XXS", max_price=5)
        assert results == []

    def test_search_price_filter(self):
        """All returned items must be at or below max_price."""
        results = search_listings("jacket", size=None, max_price=30)
        assert all(item["price"] <= 30 for item in results)

    def test_search_size_filter_case_insensitive(self):
        """Size filter should be case-insensitive."""
        results_upper = search_listings("tee", size="M", max_price=None)
        results_lower = search_listings("tee", size="m", max_price=None)
        # Both should return the same set of IDs
        ids_upper = {r["id"] for r in results_upper}
        ids_lower = {r["id"] for r in results_lower}
        assert ids_upper == ids_lower

    def test_search_results_are_dicts_with_required_fields(self):
        """Each result dict must contain the expected fields."""
        results = search_listings("vintage", size=None, max_price=None)
        assert len(results) > 0
        required_fields = {"id", "title", "description", "category", "style_tags",
                           "size", "condition", "price", "colors", "platform"}
        for item in results:
            assert required_fields.issubset(item.keys()), f"Missing fields in {item}"

    def test_search_no_zero_score_items(self):
        """Results should all have some relevance to the description."""
        results = search_listings("graphic tee", size=None, max_price=None)
        # All results should relate to graphic tees — spot check top result
        if results:
            top = results[0]
            searchable = (
                top["title"] + " " +
                top["description"] + " " +
                " ".join(top.get("style_tags", []))
            ).lower()
            assert any(kw in searchable for kw in ["graphic", "tee", "shirt", "top"])

    def test_search_no_price_filter_returns_more_results(self):
        """Removing the price filter should return at least as many results."""
        filtered = search_listings("jacket", size=None, max_price=30)
        unfiltered = search_listings("jacket", size=None, max_price=None)
        assert len(unfiltered) >= len(filtered)

    def test_search_empty_description_does_not_crash(self):
        """Empty description string should not raise an exception."""
        results = search_listings("", size=None, max_price=None)
        assert isinstance(results, list)


# ─────────────────────────────────────────────────
# Tool 2: suggest_outfit
# ─────────────────────────────────────────────────

class TestSuggestOutfit:

    def _get_sample_item(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0, "Need at least one listing for suggest_outfit tests"
        return results[0]

    def _get_example_wardrobe(self):
        from utils.data_loader import get_example_wardrobe
        return get_example_wardrobe()

    def _get_empty_wardrobe(self):
        from utils.data_loader import get_empty_wardrobe
        return get_empty_wardrobe()

    def test_suggest_outfit_returns_nonempty_string(self):
        """Happy path: should return a non-empty string."""
        item = self._get_sample_item()
        wardrobe = self._get_example_wardrobe()
        result = suggest_outfit(item, wardrobe)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_suggest_outfit_empty_wardrobe_no_exception(self):
        """Empty wardrobe: should return general advice, not raise an exception."""
        item = self._get_sample_item()
        empty_wardrobe = self._get_empty_wardrobe()
        result = suggest_outfit(item, empty_wardrobe)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_suggest_outfit_empty_wardrobe_does_not_return_empty_string(self):
        """Empty wardrobe path must not silently return ''."""
        item = self._get_sample_item()
        empty_wardrobe = self._get_empty_wardrobe()
        result = suggest_outfit(item, empty_wardrobe)
        assert result != ""


# ─────────────────────────────────────────────────
# Tool 3: create_fit_card
# ─────────────────────────────────────────────────

class TestCreateFitCard:

    def _get_sample_item(self):
        results = search_listings("vintage graphic tee", size=None, max_price=50)
        assert len(results) > 0
        return results[0]

    def test_create_fit_card_returns_string(self):
        """Happy path: should return a non-empty string."""
        item = self._get_sample_item()
        outfit = "Pair this tee with baggy dark jeans and chunky white sneakers."
        result = create_fit_card(outfit, item)
        assert isinstance(result, str)
        assert len(result.strip()) > 0

    def test_create_fit_card_empty_outfit_returns_error_string(self):
        """Empty outfit string: must return an error message, not raise."""
        item = self._get_sample_item()
        result = create_fit_card("", item)
        assert isinstance(result, str)
        assert len(result.strip()) > 0
        # Should be an error description, not a caption
        result_lower = result.lower()
        assert any(word in result_lower for word in ["cannot", "missing", "failed", "error"])

    def test_create_fit_card_whitespace_outfit_returns_error_string(self):
        """Whitespace-only outfit string: must return an error message."""
        item = self._get_sample_item()
        result = create_fit_card("   \n\t  ", item)
        assert isinstance(result, str)
        result_lower = result.lower()
        assert any(word in result_lower for word in ["cannot", "missing", "failed", "error"])

    def test_create_fit_card_does_not_raise_on_empty_outfit(self):
        """Empty outfit must not raise any exception."""
        item = self._get_sample_item()
        try:
            create_fit_card("", item)
        except Exception as e:
            raise AssertionError(f"create_fit_card raised an exception: {e}")