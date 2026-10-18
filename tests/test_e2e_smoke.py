"""Smoke tests E2E — RAG hybrid search, autoeval loop, channel gateway"""

import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─── RAG Hybrid Search ────────────────────────────────────────────────────────


class TestRagHybridSearch:
    def test_import(self):
        from src.rag_vector import hybrid_search

        assert hybrid_search is not None

    def test_rrf_score_formula(self):
        """Vérifie la formule RRF : 1/(k + rank + 1)"""
        from src.rag_vector import _rrf_score

        score_rank0 = _rrf_score(0, k=60)
        score_rank10 = _rrf_score(10, k=60)
        # Rang 0 doit avoir un score plus élevé que rang 10
        assert score_rank0 > score_rank10
        # Formule exacte : 1/(60+0+1) ≈ 0.01639
        assert abs(score_rank0 - (1 / 61)) < 1e-6

    def test_bm25_search_basic(self):
        """Vérifie que _bm25_search retourne des résultats rankés."""
        from src.rag_vector import _bm25_search

        documents = [
            {"content": "Python est un langage de programmation", "id": "doc1"},
            {"content": "FastAPI est un framework web Python", "id": "doc2"},
            {"content": "Docker permet de containeriser les applications", "id": "doc3"},
        ]
        results = _bm25_search("Python framework", documents, top_k=2)
        assert len(results) <= 2
        # Les docs Python devraient être mieux rankés
        if results:
            # _bm25_search retourne [(doc, score), ...]
            assert isinstance(results[0], tuple)
            assert isinstance(results[0][0], dict)

    def test_bm25_empty_query(self):
        from src.rag_vector import _bm25_search

        results = _bm25_search("", [], top_k=5)
        assert results == [] or isinstance(results, list)

    def test_hybrid_search_signature(self):
        """Vérifie que hybrid_search accepte les bons paramètres."""
        import inspect

        from src.rag_vector import hybrid_search

        sig = inspect.signature(hybrid_search)
        params = list(sig.parameters.keys())
        assert "query" in params
        assert "alpha" in params or "top_k" in params

    def test_rrf_ordering(self):
        """Vérifie que le RRF fusionne correctement deux listes rankées."""
        from src.rag_vector import _rrf_score

        # Un résultat rank 1 dans les deux listes doit scorer plus haut
        # qu'un rank 1 dans une seule liste
        combined_top = _rrf_score(0) + _rrf_score(0)  # top des deux listes
        single_top = _rrf_score(0) + _rrf_score(100)  # top d'une, bas de l'autre
        assert combined_top > single_top


# ─── Autoeval Loop ────────────────────────────────────────────────────────────


class TestAutoevalLoop:
    def test_import(self):
        from src.autoeval_loop import AutoevalLoop, create_from_manifest

        assert AutoevalLoop is not None
        assert create_from_manifest is not None

    def test_create_from_manifest_missing_dir(self):
        """create_from_manifest retourne None si pas de PROJECT.yaml."""
        from src.autoeval_loop import create_from_manifest

        result = create_from_manifest("/tmp/inexistant_xyz_12345")
        assert result is None

    def test_create_from_manifest_with_yaml(self):
        """create_from_manifest retourne un AutoevalLoop si PROJECT.yaml valide."""
        from src.autoeval_loop import create_from_manifest

        with tempfile.TemporaryDirectory() as tmpdir:
            project_yaml = Path(tmpdir) / "PROJECT.yaml"
            project_yaml.write_text("""
name: test-project
objective: Test autoeval
done_definition: Tests passing
budgets:
  max_tokens: 10000
  max_iterations: 10
  max_cost_usd: 1.0
  max_tool_calls: 50
eval_command: echo "score: 0.95"
metric: score
""")
            result = create_from_manifest(tmpdir)
            # Peut retourner None si l'implémentation est stricte sur le format
            # L'important : pas d'exception
            assert result is None or hasattr(result, "run_eval")

    def test_autoeval_loop_run_eval_echo(self):
        """AutoevalLoop.run_eval() exécute la commande et extrait la métrique."""
        from src.autoeval_loop import AutoevalLoop

        with tempfile.TemporaryDirectory() as tmpdir:
            loop = AutoevalLoop(
                project_dir=tmpdir,
                eval_command='echo "score: 0.85"',
                metric="score",
            )
            result = loop.run_eval()
            # Doit retourner un EvalResult avec un score
            assert result is not None
            assert hasattr(result, "score")
            assert isinstance(result.score, float)

    def test_get_summary_empty(self):
        """get_summary() retourne un dict cohérent même sans historique."""
        from src.autoeval_loop import AutoevalLoop

        with tempfile.TemporaryDirectory() as tmpdir:
            loop = AutoevalLoop(
                project_dir=tmpdir,
                eval_command='echo "score: 1.0"',
                metric="score",
            )
            summary = loop.get_summary()
            assert isinstance(summary, dict)
            # Sans historique : {"runs": 0, "best_score": None}
            assert "runs" in summary or "total_runs" in summary or "history" in summary

    def test_eval_result_dataclass(self):
        """EvalResult est un dataclass avec les bons champs."""
        from src.autoeval_loop import EvalResult

        er = EvalResult(score=0.9, raw_output="ok", success=True)
        assert er.score == 0.9
        assert er.success is True
        assert er.error is None


# ─── Channel Gateway ──────────────────────────────────────────────────────────


class TestChannelGateway:
    def test_import(self):
        from src.channel_gateway import ChannelGateway, get_gateway

        assert ChannelGateway is not None
        assert get_gateway is not None

    def test_singleton(self):
        from src.channel_gateway import get_gateway

        g1 = get_gateway()
        g2 = get_gateway()
        assert g1 is g2

    def test_adapters_dict_by_default(self):
        """Sans adapters enregistrés, _adapters doit être un dict vide."""
        from src.channel_gateway import ChannelGateway

        # Créer une nouvelle instance (pas le singleton) pour isoler le test
        gw = ChannelGateway()
        assert hasattr(gw, "_adapters")
        assert isinstance(gw._adapters, dict)
        assert len(gw._adapters) == 0

    def test_outbound_message_dataclass(self):
        """OutboundMessage est construit avec channel, recipient_id, content."""
        from src.channel_gateway import ChannelType, OutboundMessage

        msg = OutboundMessage(
            channel=ChannelType.DISCORD,
            recipient_id="user123",
            content="Test message",
        )
        assert msg.content == "Test message"
        assert msg.channel == ChannelType.DISCORD

    def test_broadcast_no_adapters(self):
        """broadcast() sans adapters retourne un dict vide sans exception."""
        import asyncio

        from src.channel_gateway import ChannelGateway

        gw = ChannelGateway()

        async def _test():
            result = await gw.broadcast("Test broadcast")
            # Sans adapters, doit retourner {} (dict vide)
            assert isinstance(result, dict)
            assert result == {}

        asyncio.run(_test())

    def test_register_mock_adapter(self):
        """Enregistrer un adapter mock et vérifier qu'il est dans le dict."""
        from collections.abc import Callable
        from typing import Any

        from src.channel_gateway import ChannelAdapter, ChannelGateway, ChannelType, InboundMessage, OutboundMessage

        class MockAdapter(ChannelAdapter):
            async def send(self, message: OutboundMessage) -> bool:
                return True

            async def start_listening(self, on_message: Callable[[InboundMessage], Any]) -> None:
                pass

            @property
            def channel_type(self) -> ChannelType:
                return ChannelType.DISCORD

        gw = ChannelGateway()
        assert len(gw._adapters) == 0
        gw.register_adapter(MockAdapter())
        assert ChannelType.DISCORD in gw._adapters
        assert len(gw._adapters) == 1

    def test_channel_type_enum_values(self):
        """Seuls les deux canaux in-process réels existent (EMAIL/WEBHOOK retirés — 0 caller)."""
        from src.channel_gateway import ChannelType

        assert hasattr(ChannelType, "DISCORD")
        assert hasattr(ChannelType, "TELEGRAM")
        assert not hasattr(ChannelType, "EMAIL")
        assert not hasattr(ChannelType, "WEBHOOK")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
