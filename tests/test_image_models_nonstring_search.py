from services.hwfit import image_models

rank_image_models = image_models.rank_image_models
IMAGE_MODEL_REGISTRY = image_models.IMAGE_MODEL_REGISTRY

SYS = {"gpu_vram_gb": 0, "has_gpu": False}


def _disable_hf_discovery(monkeypatch):
    monkeypatch.setattr(image_models, "_fetch_hf_image_collection_models", lambda: [])
    monkeypatch.setattr(image_models, "_discover_quant_repos", lambda *a, **k: {})


def test_rank_image_models_handles_non_string_search(monkeypatch):
    _disable_hf_discovery(monkeypatch)
    # search is a CLI/API filter arg; a non-string made search.lower() raise
    # AttributeError. A non-string search should behave as "no filter".
    out = rank_image_models(SYS, search=123)
    assert len(out) == len(IMAGE_MODEL_REGISTRY)


def test_rank_image_models_string_filter_still_applies(monkeypatch):
    _disable_hf_discovery(monkeypatch)
    out = rank_image_models(SYS, search="zzzznotarealmodelzzz")
    assert out == []


def test_rank_image_models_uses_ram_budget_when_gpu_disabled(monkeypatch):
    model = {
        "id": "example-org/example-image-model",
        "name": "Example Image Model",
        "provider": "example-org",
        "params_b": 20.0,
        "vram_bf16": 42.0,
        "vram_fp8": 22.0,
        "vram_q4": 14.0,
        "default_quant": "FP8",
        "quant_repos": {},
        "capabilities": ["text-to-image"],
        "description": "Imported from test fixture.",
        "quality": 80,
        "speed": 50,
    }
    monkeypatch.setattr(image_models, "_fetch_hf_image_collection_models", lambda: [model])
    monkeypatch.setattr(image_models, "_discover_quant_repos", lambda *a, **k: {})

    gpu_out = rank_image_models({"has_gpu": True, "gpu_vram_gb": 8, "available_ram_gb": 64}, search="Example Image")
    ram_out = rank_image_models({"has_gpu": False, "gpu_vram_gb": 0, "available_ram_gb": 64}, search="Example Image")

    gpu_model = next(m for m in gpu_out if m["id"] == "example-org/example-image-model")
    ram_model = next(m for m in ram_out if m["id"] == "example-org/example-image-model")

    assert gpu_model["fit"] == "no_fit"
    assert gpu_model["quant"] == "FP8"
    assert gpu_model["fit_budget"] == "gpu"
    assert ram_model["fit"] in {"good", "perfect"}
    assert ram_model["quant"] == "BF16"
    assert ram_model["fit_budget"] == "ram"


def test_mlx_image_collection_models_only_show_on_apple(monkeypatch):
    mlx_model = {
        "id": "mlx-community/example-apple-image-model",
        "name": "Example Apple Image Model",
        "provider": "mlx-community",
        "params_b": 4.0,
        "vram_bf16": 10.0,
        "vram_fp8": None,
        "vram_q4": None,
        "default_quant": "BF16",
        "quant_repos": {},
        "capabilities": ["text-to-image"],
        "description": "Apple Silicon / MLX only.",
        "quality": 82,
        "speed": 88,
        "mlx_only": True,
    }
    monkeypatch.setattr(image_models, "_fetch_hf_image_collection_models", lambda: [mlx_model])
    monkeypatch.setattr(image_models, "_discover_quant_repos", lambda *a, **k: {})

    cuda = rank_image_models({"has_gpu": True, "gpu_vram_gb": 48, "backend": "cuda"}, search="Example Apple")
    metal = rank_image_models(
        {"has_gpu": True, "gpu_vram_gb": 48, "backend": "metal", "unified_memory": True},
        search="Example Apple",
    )

    assert cuda == []
    assert [m["id"] for m in metal] == ["mlx-community/example-apple-image-model"]


def test_apple_image_mode_hides_non_mlx_models(monkeypatch):
    model = {
        "id": "example-org/example-image-model",
        "name": "Example Image Model",
        "provider": "example-org",
        "params_b": 4.0,
        "vram_bf16": 8.0,
        "vram_fp8": None,
        "vram_q4": None,
        "default_quant": "BF16",
        "quant_repos": {},
        "capabilities": ["text-to-image"],
        "description": "Imported from test fixture.",
        "quality": 80,
        "speed": 80,
    }
    monkeypatch.setattr(image_models, "_fetch_hf_image_collection_models", lambda: [model])
    monkeypatch.setattr(image_models, "_discover_quant_repos", lambda *a, **k: {})

    metal = rank_image_models(
        {"has_gpu": True, "gpu_vram_gb": 48, "backend": "metal", "unified_memory": True},
        search="Example Image",
    )
    cuda = rank_image_models(
        {"has_gpu": True, "gpu_vram_gb": 48, "backend": "cuda"},
        search="Example Image",
    )

    assert metal == []
    assert [m["id"] for m in cuda] == ["example-org/example-image-model"]


def test_mlx_collection_imports_show_on_metal_not_cuda(monkeypatch):
    mlx_model = image_models._collection_item_to_model(
        {"id": "mlx-community/example-image-model-4bit"},
        "Example Apple image collection",
        mlx_only=True,
    )
    monkeypatch.setattr(image_models, "_fetch_hf_image_collection_models", lambda: [mlx_model])
    monkeypatch.setattr(image_models, "_discover_quant_repos", lambda *a, **k: {})

    metal = rank_image_models(
        {"has_gpu": True, "gpu_vram_gb": 64, "backend": "metal", "unified_memory": True},
        search="example-image-model",
    )
    cuda = rank_image_models(
        {"has_gpu": True, "gpu_vram_gb": 64, "backend": "cuda"},
        search="example-image-model",
    )

    assert [m["id"] for m in metal] == ["mlx-community/example-image-model-4bit"]
    assert cuda == []
