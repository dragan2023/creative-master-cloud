"""Async vector retrieval paths must move synchronous calls off the loop."""

import asyncio
import importlib
import threading

import pytest

from app.services.novel_writer.project_knowledge_base.impl.mixins.retrieve_for_revision import (
    RetrieveForRevisionMixin,
)
from app.services.novel_writer.project_knowledge_base.impl.mixins.retrieve_global_only import (
    RetrieveGlobalOnlyMixin,
)


memory_module = importlib.import_module("app.agents.memory_manager")


class NullLogger:
    def info(self, *args, **kwargs):
        pass

    def warning(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class GatedVectorStore:
    def __init__(self, responses):
        self.responses = list(responses)
        self.started = [threading.Event() for _ in responses]
        self.release = [threading.Event() for _ in responses]
        self.calls = []
        self._lock = threading.Lock()
        self._next_call = 0

    def _invoke(self, kind, kwargs):
        with self._lock:
            index = self._next_call
            self._next_call += 1
            expected_kind, response = self.responses[index]
            assert kind == expected_kind
            self.calls.append((kind, kwargs))
        self.started[index].set()
        self.release[index].wait()
        return response

    def query(self, **kwargs):
        return self._invoke("query", kwargs)

    def count_documents(self, collection_name):
        return self._invoke("count", {"collection_name": collection_name})


async def _run_with_heartbeats(coroutine, vector_store):
    heartbeat_signals = [threading.Event() for _ in vector_store.responses]
    heartbeat_preceded_release = []
    watchdog_failure = []

    def watchdog():
        for index, started in enumerate(vector_store.started):
            if not started.wait(1.0):
                watchdog_failure.append(f"call {index} never started")
                vector_store.release[index].set()
                continue
            heartbeat_preceded_release.append(
                heartbeat_signals[index].wait(0.1)
            )
            vector_store.release[index].set()

    watchdog_thread = threading.Thread(target=watchdog, name="vector-test-watchdog")
    watchdog_thread.start()

    async def heartbeat():
        for index, started in enumerate(vector_store.started):
            assert await asyncio.to_thread(started.wait, 1.0)
            await asyncio.sleep(0)
            heartbeat_signals[index].set()

    try:
        result, _ = await asyncio.gather(coroutine, heartbeat())
    finally:
        for release in vector_store.release:
            release.set()
        await asyncio.to_thread(watchdog_thread.join, 1.0)

    assert not watchdog_thread.is_alive()
    assert watchdog_failure == []
    return result, heartbeat_preceded_release


@pytest.mark.asyncio
async def test_memory_search_preserves_fields_and_allows_heartbeat(monkeypatch):
    raw_result = {
        "documents": [["memory-a", "memory-b"]],
        "metadatas": [[{"rank": 1}, {"rank": 2}]],
        "distances": [[0.1, 0.2]],
    }
    fake_store = GatedVectorStore([("query", raw_result)])
    monkeypatch.setattr(memory_module, "vector_store", fake_store)
    manager = object.__new__(memory_module.MemoryManager)

    result, heartbeat_order = await _run_with_heartbeats(
        manager.search_long_term_memory(7, "dragon", n_results=2),
        fake_store,
    )

    assert heartbeat_order == [True]
    assert fake_store.calls == [
        (
            "query",
            {
                "collection_name": "user_7_memory",
                "query_texts": ["dragon"],
                "n_results": 2,
            },
        )
    ]
    assert result == [
        {"content": "memory-a", "metadata": {"rank": 1}, "distance": 0.1},
        {"content": "memory-b", "metadata": {"rank": 2}, "distance": 0.2},
    ]


class GlobalHarness(RetrieveGlobalOnlyMixin):
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.logger = NullLogger()

    def get_collection_name(self, project_id):
        return f"project_{project_id}"

    async def repair_kb_vector_store(self, project_id):
        return {"success": True, "message": "repaired"}


@pytest.mark.asyncio
async def test_global_retrieval_wraps_initial_and_repair_queries_without_changes():
    repaired_empty = {"_repaired_empty": True, "documents": [[]]}
    repaired_result = {
        "documents": [["Alice", "Alice trusts Bob"]],
        "metadatas": [[
            {"entity_type": "character", "rank": 1},
            {"entity_type": "relationship", "rank": 2},
        ]],
    }
    fake_store = GatedVectorStore(
        [("query", repaired_empty), ("query", repaired_result)]
    )
    harness = GlobalHarness(fake_store)

    result, heartbeat_order = await _run_with_heartbeats(
        harness.retrieve_global_only(11, "Alice", n_results=4),
        fake_store,
    )

    assert heartbeat_order == [True, True]
    expected_kwargs = {
        "collection_name": "project_11",
        "query_texts": ["Alice"],
        "n_results": 4,
        "where": {"doc_type": "global"},
    }
    assert fake_store.calls == [("query", expected_kwargs), ("query", expected_kwargs)]
    assert result == {
        "entities": [
            {
                "content": "Alice",
                "metadata": {"entity_type": "character", "rank": 1},
            }
        ],
        "relations": [
            {
                "content": "Alice trusts Bob",
                "metadata": {"entity_type": "relationship", "rank": 2},
            }
        ],
        "combined_context": "【人物与实体】\nAlice\n\n【关系网络】\nAlice trusts Bob",
    }


class RevisionHarness(RetrieveForRevisionMixin):
    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.logger = NullLogger()

    def get_collection_name(self, project_id):
        return f"project_{project_id}"

    def _get_event_timeline(self, project_id, current_unit):
        return ""

    def _retrieve_from_graph_files(self, project_id, current_unit, result):
        raise AssertionError("non-empty vector results must not use file fallback")


@pytest.mark.asyncio
async def test_revision_retrieval_wraps_count_and_both_queries_without_changes():
    global_result = {
        "documents": [["Alice", "Alice trusts Bob"]],
        "metadatas": [[
            {"entity_type": "character", "rank": 1},
            {"entity_type": "relationship", "rank": 2},
        ]],
    }
    unit_result = {
        "documents": [["Castle", "Alice fights"]],
        "metadatas": [[
            {"entity_type": "place", "unit_number": 3},
            {"entity_type": "relationship", "unit_number": 3},
        ]],
    }
    fake_store = GatedVectorStore(
        [("count", 4), ("query", global_result), ("query", unit_result)]
    )
    harness = RevisionHarness(fake_store)

    result, heartbeat_order = await _run_with_heartbeats(
        harness.retrieve_for_revision(11, 3, "Alice", n_results=6),
        fake_store,
    )

    assert heartbeat_order == [True, True, True]
    assert fake_store.calls == [
        ("count", {"collection_name": "project_11"}),
        (
            "query",
            {
                "collection_name": "project_11",
                "query_texts": ["Alice"],
                "n_results": 6,
                "where": {"doc_type": "global"},
            },
        ),
        (
            "query",
            {
                "collection_name": "project_11",
                "query_texts": ["Alice"],
                "n_results": 6,
                "where": {
                    "$and": [
                        {"doc_type": "unit"},
                        {"unit_number": 3},
                    ]
                },
            },
        ),
    ]
    assert result == {
        "global_entities": [
            {
                "content": "Alice",
                "metadata": {"entity_type": "character", "rank": 1},
            }
        ],
        "global_relations": [
            {
                "content": "Alice trusts Bob",
                "metadata": {"entity_type": "relationship", "rank": 2},
            }
        ],
        "unit_entities": [
            {
                "content": "Castle",
                "metadata": {"entity_type": "place", "unit_number": 3},
            }
        ],
        "unit_relations": [
            {
                "content": "Alice fights",
                "metadata": {"entity_type": "relationship", "unit_number": 3},
            }
        ],
        "combined_context": (
            "【全局设定 - 人物与实体】\nAlice\n\n"
            "【全局设定 - 关系网络】\nAlice trusts Bob\n\n"
            "【本单元 - 人物与实体】\nCastle\n\n"
            "【本单元 - 关系动态】\nAlice fights"
        ),
    }
