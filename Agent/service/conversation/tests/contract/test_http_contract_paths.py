from app.bootstrap.app_factory import create_app


def test_conversation_contract_paths_are_registered_under_service_prefix() -> None:
    schema = create_app().openapi()

    expected_paths = {
        "/api/conversation_service/v1/conversations",
        "/api/conversation_service/v1/conversations/{conversation_id}",
        "/api/conversation_service/v1/conversations/{conversation_id}/archive",
        "/api/conversation_service/v1/conversations/{conversation_id}/restore",
        "/api/conversation_service/v1/conversations/{conversation_id}/copy-config",
        "/api/conversation_service/v1/conversations/{conversation_id}/messages",
        "/api/conversation_service/v1/conversations/{conversation_id}/context",
        "/api/conversation_service/v1/conversations/{conversation_id}/reasoning-traces",
        "/api/conversation_service/v1/conversations/{conversation_id}/events",
        "/api/conversation_service/v1/runs",
    }

    assert expected_paths.issubset(set(schema["paths"]))


def test_conversation_search_does_not_use_standalone_search_path() -> None:
    schema = create_app().openapi()

    assert "/api/conversation_service/v1/conversations/search" not in schema["paths"]
    assert "/api/conversation_service/v1/search" not in schema["paths"]


def test_ag_ui_uses_runs_endpoint_without_legacy_ag_ui_path() -> None:
    schema = create_app().openapi()

    assert "post" in schema["paths"]["/api/conversation_service/v1/runs"]
    assert "/api/conversation_service/v1/conversations/{conversation_id}/ag-ui" not in schema[
        "paths"
    ]
