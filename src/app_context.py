"""AppContext — contexte d'exécution unique remplaçant les singletons globaux.

Ce module remplace l'ancien pattern `global _x = ...` dans 30+ fichiers.
L'instance est créée au démarrage (lazy) et partagée via import.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Caches:
    """Conteneur pour tous les caches globaux."""

    # provenance_memory._fs
    fs: Any = None

    # content_security._guard, _discovery
    guard: Any = None
    discovery: Any = None

    # settings._settings_cache, _features_cache
    settings_cache: Any = None
    features_cache: Any = None

    # durable_execution._executor
    executor: Any = None

    # event_bus._bus, _task_scheduler
    bus: Any = None
    task_scheduler: Any = None

    # chroma_client._client
    chroma_client: Any = None

    # data_classification._engine
    classification_engine: Any = None

    # decision_engine._decision_engine
    decision_engine: Any = None

    # embeddings._http_embed_down
    http_embed_down: Any = None

    # model_discovery._hosts_cache, _hosts_cache_time
    hosts_cache: Any = None
    hosts_cache_time: Any = None

    # observer._persistent_reports, _persistent_harness_touched
    persistent_reports: Any = None
    persistent_harness_touched: Any = None

    # opencode_client._daemon_client
    daemon_client: Any = None

    # output_router._router
    router: Any = None

    # planning_engine._engine
    planning_engine: Any = None

    # preferences._store, _resolution
    store: Any = None
    resolution: Any = None

    # progressive_disclosure._disclosure
    disclosure: Any = None

    # rag_singleton.rag_instance, _last_attempt
    rag_instance: Any = None
    rag_last_attempt: Any = None

    # secret_storage._fernet
    fernet: Any = None

    # tool_implementations._active_email_ref
    active_email_ref: Any = None

    # tool_index._tool_index, _last_attempt
    tool_index: Any = None
    tool_index_last_attempt: Any = None

    # tool_utils._mcp_manager
    mcp_manager: Any = None

    # zen_router._routing_config, _routing_config_mtime
    routing_config: Any = None
    routing_config_mtime: Any = None

    # agent_tools/document_tools._active_document_id, _active_model
    active_document_id: Any = None
    active_model: Any = None

    # agentseal_runner._agentseal_instance
    agentseal_instance: Any = None

    # ai_interaction : 5 managers
    session_manager: Any = None
    memory_manager: Any = None
    memory_vector: Any = None
    rag_manager: Any = None
    personal_docs_manager: Any = None

    # assistant_log._session_manager
    assistant_log_session_manager: Any = None

    # bg_monitor._monitor_task
    monitor_task: Any = None

    # channel_gateway._gateway_instance
    gateway_instance: Any = None

    # memory_impact._verifier
    verifier: Any = None

    # memory_provider._active_registry
    active_registry: Any = None

    # DatabaseProtocol instance (MOD-6)
    database: Any = None

    # Extensible : tout autre singleton ajouté dynamiquement
    _extra: dict[str, Any] = field(default_factory=dict)

    def __getattr__(self, name: str) -> Any:
        if name in self._extra:
            return self._extra[name]
        raise AttributeError(f"Caches n'a pas d'attribut {name!r}")

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.__dataclass_fields__ or name == "_extra":
            super().__setattr__(name, value)
        else:
            self._extra[name] = value


class AppContext:
    """Point d'accès unique aux singletons de l'application.

    Remplace tous les patterns :
        global _x
        if _x is None:
            _x = creer_x()
        return _x

    Par :
        ctx = AppContext()
        if ctx.caches.x is None:
            ctx.caches.x = creer_x()
        return ctx.caches.x
    """

    _instance: "AppContext | None" = None
    _lock = threading.RLock()

    def __new__(cls) -> "AppContext":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._caches = Caches()
                cls._instance._init_lock = threading.RLock()
            return cls._instance

    def __init__(self) -> None:
        # Appelé une seule fois grâce au singleton
        pass

    @property
    def caches(self) -> Caches:
        return self._caches

    # Accesseurs de compatibilité pour les trois catégories citées dans le plan
    @property
    def fs(self):
        return self._caches.fs

    @fs.setter
    def fs(self, value):
        self._caches.fs = value

    @property
    def guard(self):
        return self._caches.guard

    @guard.setter
    def guard(self, value):
        self._caches.guard = value

    @property
    def database(self) -> Any:
        """Accès au DatabaseProtocol via AppContext (MOD-6)."""
        if self._caches.database is None:
            from src.database_impl import get_database
            self._caches.database = get_database()
        return self._caches.database

    @database.setter
    def database(self, value):
        self._caches.database = value

    @property
    def caches_container(self):
        return self._caches

    # Méthode pour reset (tests)
    # Important : on NE REMPLACE PAS l'instance (cls._instance = None)
    # car 30+ modules ont importé `app_context` au niveau module et
    # gardent une référence vers cette instance. Si on la remplace,
    # leurs références deviennent obsolètes. À la place, on VIDE
    # les caches de l'instance existante.
    @classmethod
    def _reset_for_tests(cls) -> None:
        with cls._lock:
            if cls._instance is not None:
                # Créer un nouveau conteneur de caches vide
                cls._instance._caches = Caches()


# Instance par défaut, créée à l'import
app_context = AppContext()