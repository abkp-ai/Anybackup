from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ag_ui_mq_core import (  # noqa: E402
    ContractValidationError,
    dump_json,
    generate_valid_message_from_event,
    load_json_text,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a Decision Agent MQ message carrying a standard AG-UI event."
    )
    parser.add_argument("--event-type", required=True, help="AG-UI event type.")
    parser.add_argument("--conversation-id", required=True, help="Conversation id.")
    parser.add_argument("--turn-id", required=True, help="Source user turn/message id.")
    parser.add_argument("--sequence", type=int, required=True, help="Positive output sequence.")
    parser.add_argument("--message-id", required=True, help="Output message id.")
    parser.add_argument("--run-id", required=True, help="AG-UI run id.")
    parser.add_argument("--state-json", default=None, help="STATE_SNAPSHOT state JSON.")
    parser.add_argument("--result-json", default=None, help="TOOL_CALL_RESULT result JSON.")
    parser.add_argument("--event-id", default=None, help="MQ event id.")
    parser.add_argument("--occurred-at", default=None, help="ISO-8601 event timestamp.")
    parser.add_argument("--now-ms", type=int, default=None, help="Fixed millisecond timestamp.")
    parser.add_argument(
        "--source-service",
        default="decision_agent_session",
        help="Message source_service.",
    )
    parser.add_argument(
        "--snowflake-epoch-ms",
        type=int,
        default=1_735_689_600_000,
        help="Snowflake epoch milliseconds shared with the conversation service.",
    )
    args = parser.parse_args(argv)

    try:
        message = generate_valid_message_from_event(
            event_type=args.event_type,
            conversation_id=args.conversation_id,
            turn_id=args.turn_id,
            message_id=args.message_id,
            run_id=args.run_id,
            sequence=args.sequence,
            event_id=args.event_id,
            occurred_at=args.occurred_at,
            now_ms=args.now_ms,
            source_service=args.source_service,
            state=load_json_text(args.state_json) if args.state_json is not None else None,
            result=load_json_text(args.result_json) if args.result_json is not None else None,
        )
    except ContractValidationError as exc:
        for issue in exc.errors:
            print(issue, file=sys.stderr)
        return 1

    print(dump_json(message))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
