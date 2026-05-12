from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RunAgentMessage(StrictSchema):
    role: Literal["user", "assistant"]
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


class AgentCapabilitiesIdentity(StrictSchema):
    agentId: str
    name: str


class AgentCapabilitiesTransport(StrictSchema):
    sse: bool = True


class AgentCapabilitiesTools(StrictSchema):
    supported: bool = True
    items: list[dict[str, object]] = Field(default_factory=list)


class AgentCapabilitiesOutput(StrictSchema):
    text: bool = True
    activity: bool = True


class AgentCapabilitiesState(StrictSchema):
    snapshots: bool = True
    deltas: bool = True
    persistentState: bool = False


class AgentCapabilitiesHumanInTheLoop(StrictSchema):
    supported: bool = True
    modes: list[Literal["tool_approval", "selection_snapshot"]]


class AgentCapabilities(StrictSchema):
    identity: AgentCapabilitiesIdentity
    transport: AgentCapabilitiesTransport = Field(default_factory=AgentCapabilitiesTransport)
    tools: AgentCapabilitiesTools = Field(default_factory=AgentCapabilitiesTools)
    output: AgentCapabilitiesOutput = Field(default_factory=AgentCapabilitiesOutput)
    state: AgentCapabilitiesState = Field(default_factory=AgentCapabilitiesState)
    humanInTheLoop: AgentCapabilitiesHumanInTheLoop
