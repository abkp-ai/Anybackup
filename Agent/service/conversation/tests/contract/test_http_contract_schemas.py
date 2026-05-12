from app.bootstrap.app_factory import create_app


def test_key_request_and_error_schemas_match_contract_shape() -> None:
    components = create_app().openapi()["components"]["schemas"]

    create_request = components["CreateConversationRequest"]
    assert create_request["required"] == ["initial_message"]
    assert "initial_message" in create_request["properties"]
    assert "title" in create_request["properties"]
    assert "tags" in create_request["properties"]

    user_message = components["UserMessageRequest"]
    assert user_message["required"] == ["type", "content"]
    assert user_message["properties"]["type"]["const"] == "user_message"
    assert user_message["properties"]["content"]["maxLength"] == 20000

    error_response = components["ErrorResponse"]
    assert error_response["required"] == ["error", "request_id"]
    assert "trace_id" in error_response["properties"]


def test_create_conversation_route_uses_create_request_schema() -> None:
    schema = create_app().openapi()
    request_body = schema["paths"]["/api/conversation_service/v1/conversations"]["post"][
        "requestBody"
    ]

    assert request_body["content"]["application/json"]["schema"]["$ref"].endswith(
        "/CreateConversationRequest"
    )


def test_patch_conversation_route_uses_update_request_schema() -> None:
    schema = create_app().openapi()
    request_body = schema["paths"]["/api/conversation_service/v1/conversations/{conversation_id}"][
        "patch"
    ]["requestBody"]

    assert request_body["content"]["application/json"]["schema"]["$ref"].endswith(
        "/UpdateConversationRequest"
    )


def test_update_conversation_request_requires_title() -> None:
    components = create_app().openapi()["components"]["schemas"]
    update_request = components["UpdateConversationRequest"]

    assert update_request["required"] == ["title"]
    assert update_request["properties"]["title"]["maxLength"] == 120


def test_conversation_schemas_expose_active_run_without_legacy_interaction_state() -> None:
    components = create_app().openapi()["components"]["schemas"]

    conversation = components["ConversationResponse"]
    assert "active_run_id" in conversation["properties"]
    assert "has_active_run" in conversation["properties"]
    assert "active_turn_id" not in conversation["properties"]
    assert "interaction_status" not in conversation["properties"]

    message = components["ConversationMessageResponse"]
    assert "turn_id" in message["properties"]

    status_event = components["ConversationStatusEventResponse"]
    assert "turn_id" in status_event["properties"]
    assert "interaction_status" not in status_event["properties"]

    events_response = components["ConversationEventsResponse"]
    assert set(events_response["required"]) >= {
        "items",
        "page",
        "latest_sequence",
        "recommended_poll_interval_ms",
    }
    assert "interaction_status" not in events_response["properties"]


def test_run_agent_input_uses_state_not_snapshot() -> None:
    components = create_app().openapi()["components"]["schemas"]

    run_input = components["RunAgentInput"]
    assert "threadId" in run_input["properties"]
    assert "runId" in run_input["properties"]
    assert "state" in run_input["properties"]
    assert "snapshot" not in run_input["properties"]
