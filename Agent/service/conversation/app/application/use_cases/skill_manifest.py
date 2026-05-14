from typing import Any

AUTH_REQUIREMENT = {
    "identity_source": "nginx_ingress_x_user",
    "phase": "P0",
    "permission_model": "unified_backup_admin",
    "required_roles": ["backup_admin"],
}


class GetSkillManifestHandler:
    def __init__(self, *, api_prefix: str, service_version: str) -> None:
        self._api_prefix = api_prefix
        self._service_version = service_version

    async def handle(self) -> dict[str, Any]:
        capabilities = _capabilities(self._api_prefix)
        return {
            "skill_manifest": {
                "schema_version": "conversation.skill_manifest.v1",
                "service_name": "conversation_service",
                "service_version": self._service_version,
                "auth_requirement": AUTH_REQUIREMENT,
                "compatibility": {
                    "api_prefix": self._api_prefix,
                    "minimum_client_version": "0.1.0",
                    "breaking_change_policy": "semantic_versioning",
                },
                "capability_count": len(capabilities),
            },
            "capability_catalog": capabilities,
            "cli_package_metadata": {
                "package_name": "anybackup-conversation-skill",
                "version": self._service_version,
                "entrypoint": "anybackup-conversation",
                "manifest_path": f"{self._api_prefix}/skill-manifest",
            },
        }


def _capabilities(api_prefix: str) -> list[dict[str, Any]]:
    return [
        _capability(
            "conversation.create",
            "POST",
            "/conversations",
            ["CreateConversationRequest"],
            "MessageAcceptedResponse",
            api_prefix,
            idempotency_required=True,
        ),
        _capability(
            "conversation.message.send",
            "POST",
            "/conversations/{conversation_id}/messages",
            ["UserMessageRequest"],
            "MessageAcceptedResponse",
            api_prefix,
            idempotency_required=True,
        ),
        _mq_capability(
            "conversation.decision_agent.bizdata.publish",
            "decision_agent.bizdata.events",
            "decision_agent.session.business_data.v1",
            ["DecisionAgentBusinessDataEnvelope"],
            "ConversationMessage.business_data",
            api_prefix,
        ),
        _capability(
            "conversation.candidate_selection.submit",
            "POST",
            "/conversations/{conversation_id}/candidate-selections",
            ["CandidateSelectionRequest"],
            "CandidateSelectionAcceptedResponse",
            api_prefix,
            idempotency_required=True,
        ),
        _capability(
            "conversation.archive",
            "POST",
            "/conversations/{conversation_id}/archive",
            ["ConversationArchiveRequest"],
            "ConversationResponse",
            api_prefix,
        ),
        _capability(
            "conversation.restore",
            "POST",
            "/conversations/{conversation_id}/restore",
            ["ConversationRestoreRequest"],
            "ConversationResponse",
            api_prefix,
        ),
        _capability(
            "conversation.copy_config",
            "POST",
            "/conversations/{conversation_id}/copy-config",
            ["CopyConversationConfigRequest"],
            "ConversationDetailResponse",
            api_prefix,
            idempotency_required=True,
        ),
        _capability(
            "conversation.context.get",
            "GET",
            "/conversations/{conversation_id}/context",
            [],
            "ConversationContextResponse",
            api_prefix,
        ),
        _capability(
            "conversation.events.list",
            "GET",
            "/conversations/{conversation_id}/events",
            [],
            "ConversationEventsResponse",
            api_prefix,
        ),
    ]


def _mq_capability(
    name: str,
    exchange: str,
    routing_key: str,
    parameters_schema: list[str],
    return_schema: str,
    api_prefix: str,
) -> dict[str, Any]:
    return {
        "name": name,
        "version": "v1",
        "transport": "mq",
        "exchange": exchange,
        "routing_key": routing_key,
        "parameters_schema": parameters_schema,
        "return_schema": return_schema,
        "idempotency_required": True,
        "auth_requirement": AUTH_REQUIREMENT,
        "compatibility": {
            "api_prefix": api_prefix,
            "supports_ag_ui": True,
            "supports_markdown_ag_ui": True,
            "supports_polling_events": True,
            "websocket_supported": False,
        },
    }


def _capability(
    name: str,
    method: str,
    path: str,
    parameters_schema: list[str],
    return_schema: str,
    api_prefix: str,
    *,
    idempotency_required: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "version": "v1",
        "transport": "http",
        "method": method,
        "path": f"{api_prefix}{path}",
        "parameters_schema": parameters_schema or ["path/query parameters"],
        "return_schema": return_schema,
        "idempotency_required": idempotency_required,
        "auth_requirement": AUTH_REQUIREMENT,
        "compatibility": {
            "api_prefix": api_prefix,
            "supports_ag_ui": True,
            "supports_polling_events": True,
            "websocket_supported": False,
        },
    }
