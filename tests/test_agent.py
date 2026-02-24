import json
from unittest.mock import MagicMock, patch

import pytest

from src.agent import Agent
from src.tools.base import Tool, ToolRegistry


class MockTool(Tool):
    """A simple tool for testing the agent loop without real API calls."""

    @property
    def name(self) -> str:
        return "mock_tool"

    @property
    def description(self) -> str:
        return "A mock tool for testing"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Test input"},
            },
            "required": ["input"],
        }

    def execute(self, **kwargs) -> dict:
        return {"success": True, "data": f"processed: {kwargs.get('input', '')}"}


class TestAgentSetup:
    def test_agent_initializes_with_registry(self):
        registry = ToolRegistry()
        registry.register(MockTool())
        agent = Agent(registry=registry)

        assert agent.registry is registry
        assert agent.memory.step_count == 0

    def test_build_system_prompt_includes_tools(self):
        registry = ToolRegistry()
        registry.register(MockTool())
        agent = Agent(registry=registry)

        prompt = agent._build_system_prompt()
        assert "mock_tool" in prompt
        assert "A mock tool for testing" in prompt

    def test_build_messages_with_empty_memory(self):
        registry = ToolRegistry()
        agent = Agent(registry=registry)

        messages = agent._build_messages("test task")
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "test task"


class TestToolExecution:
    def test_execute_known_tool(self):
        registry = ToolRegistry()
        registry.register(MockTool())
        agent = Agent(registry=registry)

        result = agent._execute_tool("mock_tool", {"input": "hello"})
        assert result["success"] is True
        assert result["data"] == "processed: hello"

    def test_execute_unknown_tool(self):
        registry = ToolRegistry()
        agent = Agent(registry=registry)

        result = agent._execute_tool("nonexistent", {})
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_execute_tool_handles_exception(self):
        registry = ToolRegistry()

        class FailingTool(Tool):
            @property
            def name(self):
                return "failing"

            @property
            def description(self):
                return "Always fails"

            @property
            def parameters(self):
                return {"type": "object", "properties": {}}

            def execute(self, **kwargs):
                raise ValueError("Something went wrong")

        registry.register(FailingTool())
        agent = Agent(registry=registry)

        result = agent._execute_tool("failing", {})
        assert result["success"] is False
        assert "Something went wrong" in result["error"]


class TestAgentLoop:
    @patch("src.agent.OpenAI")
    def test_agent_returns_final_answer(self, mock_openai_class):
        """Test that the agent loop terminates when LLM returns FINAL_ANSWER."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # Simulate LLM returning a final answer directly
        mock_message = MagicMock()
        mock_message.tool_calls = None
        mock_message.content = "FINAL_ANSWER\n\nHere is my analysis."

        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=mock_message)]
        mock_client.chat.completions.create.return_value = mock_response

        registry = ToolRegistry()
        agent = Agent(registry=registry)
        agent.client = mock_client

        result = agent.run("some JD", "resume.txt")
        assert "Here is my analysis." in result

    @patch("src.agent.OpenAI")
    def test_agent_calls_tool_then_finishes(self, mock_openai_class):
        """Test that the agent calls a tool, observes, then finishes."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        # First call: agent wants to use a tool
        tool_message = MagicMock()
        tool_call = MagicMock()
        tool_call.function.name = "mock_tool"
        tool_call.function.arguments = json.dumps({"input": "test"})
        tool_message.tool_calls = [tool_call]
        tool_message.content = "Let me test this"

        # Second call: agent returns final answer
        final_message = MagicMock()
        final_message.tool_calls = None
        final_message.content = "FINAL_ANSWER\n\nDone with analysis."

        mock_client.chat.completions.create.side_effect = [
            MagicMock(choices=[MagicMock(message=tool_message)]),
            MagicMock(choices=[MagicMock(message=final_message)]),
        ]

        registry = ToolRegistry()
        registry.register(MockTool())
        agent = Agent(registry=registry)
        agent.client = mock_client

        result = agent.run("some JD", "resume.txt")
        assert "Done with analysis." in result
        # Step 1 is the tool call; step 2 is the final answer (not stored)
        assert agent.memory.step_count == 1
