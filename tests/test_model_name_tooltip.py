"""Regression for issue #1982 — long model names are clipped with ellipsis in
two surfaces (the model-picker dropdown items and the chat-header model
indicator) with no tooltip, so the suffix/variant tag is undiscoverable.

The fix adds a `title` (native hover tooltip) carrying the full name to both
render sites in static/js/modelPicker.js. The module pulls in browser globals so
it can't be imported under node; this guards the two title assignments at source.
"""
import re
from pathlib import Path

SRC = (Path(__file__).resolve().parent.parent / "static/js/modelPicker.js").read_text(encoding="utf-8")


def test_dropdown_item_has_title_tooltip():
    # The dropdown item name span must carry a title with the full display name.
    assert re.search(r"nameSpan\.title\s*=\s*m\.display", SRC), \
        "dropdown model-name span needs a title tooltip (#1982)"


def test_header_indicator_has_title_tooltip():
    # updateModelPicker must set the header label's title to the full model id
    # (empty for the 'Select model' placeholder).
    body = SRC[SRC.index("export function updateModelPicker()"):]
    assert re.search(r"label\.title\s*=\s*modelId\b", body), \
        "header model indicator needs a title tooltip (#1982)"


def test_api_picker_dedupe_includes_endpoint_id():
    # API providers can expose the same model id intentionally. The chat picker
    # must not dedupe OpenRouter away just because OpenAI has the same id.
    assert "const isApiEndpoint = item.category && item.category !== 'local';" in SRC
    assert re.search(r"const seenKey = isApiEndpoint\s*\?", SRC), \
        "chat picker should dedupe API models by endpoint+model, not model id only"
    assert "${item.endpoint_id || item.url || item.endpoint_name || 'api'}::${mid}" in SRC


def test_api_picker_groups_by_endpoint_name():
    # OpenRouter models often have ids like openai/* or google/*; browse mode
    # should still show them under the OpenRouter endpoint group.
    assert "function _providerGroupKey(m)" in SRC
    assert "m.category && m.category !== 'local' && m.epName" in SRC
    assert "`~endpoint:${m.epName}`" in SRC
    assert "_providerGroupName(provider)" in SRC
