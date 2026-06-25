"""Captura de lacunas de conhecimento — telemetria fire-and-forget (não pode quebrar o agente)."""
import packages.engine.knowledge_gaps as kg


def test_failsoft_db_error_never_propagates(monkeypatch):
    monkeypatch.setattr(kg.settings, "KNOWLEDGE_GAP_CAPTURE_ENABLED", True)

    class _BoomClient:
        def rpc(self, *a, **k):
            raise RuntimeError("db down")

    monkeypatch.setattr(kg.db, "client", _BoomClient())
    # Não deve levantar — fail-soft.
    kg.record_knowledge_gap("org-1", "pergunta sem resposta")


def test_noop_when_flag_disabled(monkeypatch):
    monkeypatch.setattr(kg.settings, "KNOWLEDGE_GAP_CAPTURE_ENABLED", False)

    class _Client:
        def rpc(self, *a, **k):
            raise AssertionError("não deveria chamar o DB com a flag desligada")

    monkeypatch.setattr(kg.db, "client", _Client())
    kg.record_knowledge_gap("org-1", "x")


def test_skips_invalid_inputs(monkeypatch):
    monkeypatch.setattr(kg.settings, "KNOWLEDGE_GAP_CAPTURE_ENABLED", True)
    calls: list = []

    class _Exec:
        def execute(self):
            return None

    class _Client:
        def rpc(self, name, params):
            calls.append(params)
            return _Exec()

    monkeypatch.setattr(kg.db, "client", _Client())
    kg.record_knowledge_gap("ALL", "x")        # org ALL → ignora (cross-tenant)
    kg.record_knowledge_gap("", "x")            # org vazio → ignora
    kg.record_knowledge_gap("org-1", "   ")    # pergunta vazia → ignora
    assert calls == []


def test_calls_rpc_with_trimmed_payload(monkeypatch):
    monkeypatch.setattr(kg.settings, "KNOWLEDGE_GAP_CAPTURE_ENABLED", True)
    captured: dict = {}

    class _Exec:
        def execute(self):
            captured["executed"] = True

    class _Client:
        def rpc(self, name, params):
            captured["name"] = name
            captured["params"] = params
            return _Exec()

    monkeypatch.setattr(kg.db, "client", _Client())
    kg.record_knowledge_gap("org-1", "  Quanto custa botox?  ", "receptionist")
    assert captured["name"] == "record_knowledge_gap"
    assert captured["params"] == {
        "p_org": "org-1",
        "p_question": "Quanto custa botox?",
        "p_agent": "receptionist",
    }
    assert captured["executed"] is True
