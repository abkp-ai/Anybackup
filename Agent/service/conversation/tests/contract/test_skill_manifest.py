from fastapi.testclient import TestClient

from app.bootstrap.app_factory import create_app

API_PREFIX = "/api/conversation_service/v1"


def test_skill_manifest_endpoint_publishes_required_artifacts() -> None:
    client = TestClient(create_app())

    response = client.get(f"{API_PREFIX}/skill-manifest")

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"skill_manifest", "capability_catalog", "cli_package_metadata"}
    assert body["skill_manifest"]["schema_version"] == "conversation.skill_manifest.v1"
    assert body["skill_manifest"]["service_name"] == "conversation_service"
    assert body["skill_manifest"]["service_version"]
    assert body["skill_manifest"]["auth_requirement"] == {
        "identity_source": "nginx_ingress_x_user",
        "phase": "P0",
        "permission_model": "unified_backup_admin",
        "required_roles": ["backup_admin"],
    }
    assert body["cli_package_metadata"]["package_name"] == "anybackup-conversation-skill"
    assert body["cli_package_metadata"]["version"] == body["skill_manifest"]["service_version"]


def test_skill_manifest_capability_catalog_is_complete() -> None:
    client = TestClient(create_app())

    body = client.get(f"{API_PREFIX}/skill-manifest").json()
    capabilities = {item["name"]: item for item in body["capability_catalog"]}

    assert {
        "conversation.create",
        "conversation.message.send",
        "conversation.decision_agent.bizdata.publish",
        "conversation.candidate_selection.submit",
        "conversation.archive",
        "conversation.restore",
        "conversation.copy_config",
    }.issubset(capabilities)

    for capability in capabilities.values():
        assert capability["version"] == "v1"
        assert capability["parameters_schema"]
        assert capability["return_schema"]
        assert capability["auth_requirement"]["permission_model"] == "unified_backup_admin"
        assert capability["compatibility"]["api_prefix"] == API_PREFIX

    bizdata_publish = capabilities["conversation.decision_agent.bizdata.publish"]
    assert bizdata_publish["return_schema"] == "ConversationMessage.business_data"
    assert bizdata_publish["compatibility"]["supports_markdown_ag_ui"] is True


def test_skill_manifest_does_not_publish_out_of_scope_foundation_capability() -> None:
    client = TestClient(create_app())

    body = client.get(f"{API_PREFIX}/skill-manifest").json()
    capability_names = {item["name"] for item in body["capability_catalog"]}

    assert "foundation.execute" not in capability_names
    assert "plan.create" not in capability_names
