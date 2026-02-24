from abc import ABC, abstractmethod
from typing import Any


class Tool(ABC):
    """Base class for all agent tools.

    Every tool the agent can call must inherit from this class
    and implement the execute() method. The agent uses the name
    and description to decide which tool to invoke.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier the agent uses to select this tool."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of what this tool does.
        The agent reads this to decide when to use the tool."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> dict:
        """JSON schema describing the expected input parameters.
        Used for structured tool calling with the LLM."""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> dict[str, Any]:
        """Run the tool with the given parameters and return results."""
        pass

    def to_openai_spec(self) -> dict:
        """Convert this tool to OpenAI function calling format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolRegistry:
    """Registry that holds all available tools for the agent.

    The agent queries this registry to discover what tools it can use
    and to dispatch tool calls by name.
    """

    def __init__(self):
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        """Register a tool so the agent can use it."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        """Look up a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())

    def to_openai_specs(self) -> list[dict]:
        """Convert all tools to OpenAI function calling format."""
        return [tool.to_openai_spec() for tool in self._tools.values()]
