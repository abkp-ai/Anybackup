# Conversation Agent MQ Mock

This mock supports frontend and Conversation Service integration while Core Agent Service and Decision Agent are not ready.

It consumes Conversation Service MQ messages and publishes:

- Core status messages to `conversation.core_agent.status.v1`.
- Business data MQ messages to `decision_agent.bizdata.events` with routing key `decision_agent.session.business_data.v1`.

The mock follows the current implemented Conversation Service runtime contract for status events:

- Input exchange: `conversation.message.events`
- Input routing key: `conversation.message.sent.v1`
- Input payload must include `conversation_id`, source user `message_id`, `turn_id`,
  and `content`. The mock generates business data output `message_id` itself.
- Accepted event: `core_agent.run.accepted`
- Rejected event: `core_agent.run.rejected`
- Failed event: `core_agent.run.failed`

Business data output follows the formal MQ contract:

- Exchange: `decision_agent.bizdata.events`
- Routing key: `decision_agent.session.business_data.v1`
- Event type: `decision_agent.session.business_data`

## Configuration

| Environment variable | Default | Description |
| --- | --- | --- |
| `RABBITMQ_URL` | required | RabbitMQ connection string. |
| `CONVERSATION_EXCHANGE` | `conversation.message.events` | Exchange published by Conversation Service. |
| `CONVERSATION_ROUTING_KEY` | `conversation.message.sent.v1` | Routing key to consume. |
| `MOCK_INPUT_QUEUE` | `core-agent-mock.message.events` | Durable queue owned by this mock. |
| `CORE_STATUS_QUEUE` | `conversation.core_agent.run_status` | Queue consumed by Conversation Service status consumer. |
| `BIZDATA_EXCHANGE` | `decision_agent.bizdata.events` | Business data output exchange. |
| `BIZDATA_ROUTING_KEY` | `decision_agent.session.business_data.v1` | Business data output routing key. |
| `BIZDATA_QUEUE` | `conversation.decision_agent.bizdata` | Durable queue bound for business data debug/consumer handoff. |
| `MOCK_DELAY_MS` | `800` | Delay between simulated steps. |
| `MOCK_PREFETCH_COUNT` | `10` | RabbitMQ consumer prefetch count. |

## Local Test

```powershell
python -m unittest discover tools\conversation_agent_mq_mock\tests -v
```

## Container

```powershell
docker build -t conversation-agent-mq-mock:0.1.0 tools\conversation_agent_mq_mock
```

## Helm

```powershell
helm upgrade --install conversation-agent-mq-mock tools\conversation_agent_mq_mock\helm `
  --namespace anybackup-ai `
  --set image.repository=<registry>/conversation-agent-mq-mock `
  --set image.tag=0.1.0
```

## Deploy to 192.168.40.107

Use the kube context that targets the Kubernetes environment on `192.168.40.107`.
The chart expects `conversation-service-secrets` in namespace `anybackup-ai` and reads the RabbitMQ URL from key `rabbitmq-url`.

```powershell
docker build -t docker.aityp.com/image/docker.io/anybackup/conversation-agent-mq-mock:0.1.1 tools\conversation_agent_mq_mock
docker push docker.aityp.com/image/docker.io/anybackup/conversation-agent-mq-mock:0.1.1

helm upgrade --install conversation-agent-mq-mock tools\conversation_agent_mq_mock\helm `
  --namespace anybackup-ai `
  --create-namespace `
  --set image.registry=docker.aityp.com `
  --set image.repository=image/docker.io/anybackup/conversation-agent-mq-mock `
  --set image.tag=0.1.1

kubectl rollout status deployment/conversation-agent-mq-mock -n anybackup-ai
kubectl logs deployment/conversation-agent-mq-mock -n anybackup-ai --tail=100
```
