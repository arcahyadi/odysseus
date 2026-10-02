from services.hwfit import image_models

rank_image_models = image_models.rank_image_models
IMAGE_MODEL_REGISTRY = image_models.IMAGE_MODEL_REGISTRY


def test_rank_image_models_handles_non_dict_system(monkeypatch):
    monkeypatch.setattr(image_models, "_fetch_hf_image_collection_models", lambda: [])
    monkeypatch.setattr(image_models, "_discover_quant_repos", lambda *a, **k: {})
    # `system` is the detected-hardware dict; if detection failed and returned
    # None (or a non-dict), system.get(...) raised AttributeError. Treat a
    # non-dict system as "unknown hardware" (no GPU) rather than crashing.
    assert len(rank_image_models(None)) == len(IMAGE_MODEL_REGISTRY)
    assert len(rank_image_models(123)) == len(IMAGE_MODEL_REGISTRY)
