from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunAgentMessage(StrictSchema):
    role: Literal["user", "assistant", "system", "tool"]
    content: str | None = Field(default=None, max_length=20_000)
    id: str | None = Field(default=None, max_length=128)


class RunAgentInput(StrictSchema):
    threadId: str = Field(min_length=1, max_length=128)
    runId: str = Field(min_length=1, max_length=128)
    messages: list[RunAgentMessage] = Field(min_length=1, max_length=100)
    state: dict[str, object] | None = None
    tools: list[dict[str, object]] | None = None
    context: list[dict[str, object]] | None = None
    forwardedProps: dict[str, object] | None = None
