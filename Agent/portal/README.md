English | [中文](README_zh.md)

# AnyBackup Agent Portal Frontend

`portal` is the web frontend workspace of AnyBackup Agent.  
It focuses on the conversation workspace and related operational UI for agent-based backup workflows.

## Positioning

- **What it is**: frontend implementation for Agent portal UX.
- **Primary users**: operators and developers validating conversation-driven workflows.
- **What it is not**: not a standalone product repository and not the full AnyBackup platform.

## Open Source Scope

Currently open in this repo:

- Conversation workspace UI (chat panel, conversation list, interaction flow)
- Structured rich content rendering (including AG-UI layout-tree based rendering path)
- Frontend service layer, state management, and local development toolchain
- Unit tests for critical chat/store/service paths

## Roadmap

Planned incremental open improvements:

- Better extensibility for multimodal cards and action handlers
- Clearer API contract examples and mock data recipes for contributors
- More stable test baselines (component + integration-level)
- Continued cleanup of legacy placeholder routes

## Quick Start

Recommended:

```bash
Node.js 20.x
npm 10.x
```

Install and run:

```bash
npm install
npm run dev
```

Build and test:

```bash
npm run build
npm run test
```

## Development Configuration

For local API proxy, add to `.env.local`:

```bash
VITE_AUTH_SERVICE_PROXY_TARGET=http://<auth-service-host>
VITE_CONVERSATION_SERVICE_PROXY_TARGET=http://<conversation-service-host>
```

Proxy paths:

- `/api/auth_service`
- `/api/conversation_service`

## Project Structure

```text
src/
|-- app/          # app composition and routing
|-- pages/        # route pages
|-- components/   # reusable UI/business components
|-- services/     # API adapters and protocol parsing
|-- store/        # Zustand state and conversation flow
|-- config/       # app configuration
|-- test/         # test setup and helpers
`-- ...
```

## Documentation

- Start with `AGENTS.md`
- If your work is in `docs/**`, then follow `docs/AGENTS.md`
- If your work is in `skills/**`, then follow `skills/AGENTS.md`
- Engineering baseline and architecture docs are under `docs/`
- Detailed implementation notes are intentionally kept in docs, not this top-level README

## Related Project

- [Anybackup](https://github.com/anybackup-ai/Anybackup): full AI-native data resilience platform built on this ecosystem

## License

This project is licensed under the terms in [LICENSE](LICENSE).
