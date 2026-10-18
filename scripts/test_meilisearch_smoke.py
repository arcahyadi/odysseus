#!/usr/bin/env python3
"""Quick smoke-test: Meilisearch client kill-switch and endpoint."""

import os

# Force kill-switch OFF
os.environ["ODYSSEUS_MEILISEARCH"] = "off"

# Test 1: Client import
from services.search.meilisearch_client import is_enabled, search_all

assert is_enabled() is False, "is_enabled() should be False when kill-switch is off"
print("PASS: is_enabled() returns False when kill-switch is off")

# Test 2: search_all returns empty
result = search_all("restaurent")
assert result["hits"] == [], "search_all should return empty hits when disabled"
assert result["total"] == 0
print("PASS: search_all returns empty when disabled")

# Test 3: fulltext endpoint exists in routes
from routes.search_routes import setup_search_routes

router = setup_search_routes({})
route_paths = [r.path for r in router.routes]
assert "/api/search/fulltext" in route_paths, f"fulltext route missing, got: {route_paths}"
print("PASS: /api/search/fulltext route registered")

print("\nAll smoke tests passed!")
