import json
import os
from abc import ABC, abstractmethod
from typing import Callable

from openai import OpenAI
from dotenv import load_dotenv

from ..memory import AgentMemory, AgentStep, ToolResult
from ..tools.base import ToolRegistry
from .. import database as db

load_dotenv()

MAX_STEPS = int(os.getenv("AGENT_MAX_STEPS", "15"))

# Provider configurations
DEFAULT_PROVIDER = os.getenv("LLM_PROVIDER", "groq")

PROVIDERS = {
    "groq": {
        "base_url": "https://api.groq.com/openai/v1",
        "env_key": "GROQ_API_KEY",
        "default_model": "llama-3.3-70b-versatile",
    },
    "openai": {
        "base_url": None,
        "env_key": "OPENAI_API_KEY",
        "default_model": "gpt-4o-mini",
    },
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "env_key": "DEEPSEEK_API_KEY",
        "default_model": "deepseek-chat",
    },
    "ollama": {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "env_key": "OLLAMA_API_KEY",
        "default_model": os.getenv("LLM_MODEL", "llama3.1:8b"),
    },
}


class BaseAgent(ABC):
    """Base class for all specialized agents in the KaziAI system.

    Each agent has:
    - A name and role description
    - A set of tools it can use
    - Its own system prompt defining its expertise
    - Independent memory tracking its reasoning steps
    """

    def __init__(
        self,
        registry: ToolRegistry,
        provider: str = DEFAULT_PROVIDER,
        model: str | None = None,
    ):
        self.registry = registry
        self.memory = AgentMemory()

        config = PROVIDERS.get(provider, PROVIDERS["groq"])
        self.model = model or config["default_model"]
        self._client = None
        self._provider_config = config

    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv(self._provider_config["env_key"]) or "ollama"
            base_url = self._provider_config["base_url"]
            self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        return self._client

    @client.setter
    def client(self, value):
        self._client = value

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent identifier (e.g., 'scout', 'forge')."""
        pass

    @property
    @abstractmethod
    def role(self) -> str:
        """One-line description of what this agent does."""
        pass

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Full system prompt that defines this agent's behavior."""
        pass

    SELF_CORRECTION_PROMPT = """
SELF-CORRECTION RULES:
- If a tool call fails, analyze the error and try alternative parameters.
- If search returns no results, broaden your search terms or try synonyms.
- Never give up after a single failure — try at least one alternative approach.
- If stuck after retries, provide your best analysis with what you have.
- Always explain what you tried if something didn't work."""

    def _build_tool_descriptions(self) -> str:
        lines = []
        for tool in self.registry.list_tools():
            lines.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(lines)

    def _execute_tool_with_retry(self, name: str, arguments: dict, max_retries: int = 2) -> dict:
        """Execute a tool with automatic retry on failure."""
        result = self._execute_tool(name, arguments)
        if result.get("success", True):
            return result

        # Retry on failure
        for attempt in range(max_retries):
            print(f"    Retry {attempt + 1}/{max_retries} for {name}")
            result = self._execute_tool(name, arguments)
            if result.get("success", True):
                return result

        return result

    def _build_messages(self, task: str, bus_context: str = "", rl_hints: str = "") -> list[dict]:
        """Build message history for the LLM call."""
        prompt = self.system_prompt.format(
            tool_descriptions=self._build_tool_descriptions()
        )
        prompt += self.SELF_CORRECTION_PROMPT

        # Inject RL tool preference hints if available
        if rl_hints:
            prompt += f"\n\nTOOL OPTIMIZATION HINTS:\n{rl_hints}"

        # Inject structured context from message bus if available
        user_content = task
        if bus_context:
            user_content = task + "\n" + bus_context

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_content},
        ]

        for step in self.memory.steps:
            messages.append({
                "role": "assistant",
                "content": f"Thought: {step.thought}",
            })
            if step.tool_call:
                messages.append({
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": f"call_{step.step_number}",
                        "type": "function",
                        "function": {
                            "name": step.tool_call.tool_name,
                            "arguments": json.dumps(step.tool_call.arguments),
                        },
                    }],
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": f"call_{step.step_number}",
                    "content": json.dumps(step.tool_call.result),
                })

        return messages

    def _execute_tool(self, name: str, arguments: dict) -> dict:
        tool = self.registry.get(name)
        if tool is None:
            return {"success": False, "error": f"Unknown tool: {name}"}
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return {"success": False, "error": f"Tool failed: {str(e)}"}

    def run(
        self,
        task: str,
        trace_id: int | None = None,
        message_bus=None,
        cancel_check: Callable[[], bool] | None = None,
        on_thought: Callable[[str, str], None] | None = None,
        rl_hints: str = "",
    ) -> str:
        """Execute the agent's ReAct loop on a given task.

        Args:
            task: The task description for the agent
            trace_id: Optional trace ID for persistence to agent_steps table
            message_bus: Optional MessageBus for structured inter-agent context
            cancel_check: Optional callback returning True if execution should stop
            on_thought: Optional callback(thought, tool_name) to stream reasoning
            rl_hints: Optional RL-generated tool preference hints
        """
        self.memory.clear()
        total_tool_calls = 0
        print(f"\n--- {self.name.upper()} AGENT ---\n")

        # Build structured context from message bus if available
        bus_context = ""
        if message_bus is not None:
            bus_context = message_bus.get_context_for(self.name)

        for step_num in range(1, MAX_STEPS + 1):
            # Check for cancellation between steps
            if cancel_check and cancel_check():
                summary = self.memory.get_history_summary()
                cancel_msg = f"(cancelled after {step_num - 1} steps) {summary}"
                if trace_id:
                    try:
                        db.complete_trace(trace_id, "cancelled", cancel_msg, step_num - 1, total_tool_calls)
                    except Exception:
                        pass
                return cancel_msg

            print(f"  [{self.name}] Step {step_num}/{MAX_STEPS}")

            messages = self._build_messages(task, bus_context, rl_hints)
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.registry.to_openai_specs(),
                tool_choice="auto",
            )

            message = response.choices[0].message

            if message.tool_calls:
                tool_call = message.tool_calls[0]
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)
                thought = message.content or f"Using {func_name}"

                print(f"    Thought: {thought[:100]}")
                print(f"    Action: {func_name}")

                result = self._execute_tool_with_retry(func_name, func_args)
                observation = json.dumps(result, indent=2)
                success = result.get("success", True)
                total_tool_calls += 1

                print(f"    Result: {'OK' if success else 'FAILED'}")

                # Stream reasoning to caller
                if on_thought:
                    on_thought(thought, func_name)

                self.memory.add_step(AgentStep(
                    step_number=step_num,
                    thought=thought,
                    tool_call=ToolResult(
                        tool_name=func_name,
                        arguments=func_args,
                        result=result,
                    ),
                    observation=observation,
                ))

                # Persist step to database if tracing
                if trace_id:
                    try:
                        db.add_trace_step(
                            trace_id=trace_id,
                            step_number=step_num,
                            thought=thought,
                            tool_name=func_name,
                            tool_args=json.dumps(func_args),
                            tool_result=observation[:4000],
                            observation=observation[:2000],
                            success=success,
                        )
                    except Exception:
                        pass  # Don't let trace persistence break the agent
            else:
                content = message.content or ""
                if "FINAL_ANSWER" in content:
                    final = content.split("FINAL_ANSWER", 1)[1].strip()
                    print(f"  [{self.name}] Complete ({step_num} steps)\n")

                    # Complete the trace
                    if trace_id:
                        try:
                            db.complete_trace(trace_id, "completed", final, step_num, total_tool_calls)
                        except Exception:
                            pass

                    return final

                self.memory.add_step(AgentStep(
                    step_number=step_num,
                    thought=content,
                ))
                print(f"    Thought: {content[:150]}")

                # Persist thought step
                if trace_id:
                    try:
                        db.add_trace_step(
                            trace_id=trace_id,
                            step_number=step_num,
                            thought=content,
                        )
                    except Exception:
                        pass

        print(f"  [{self.name}] Max steps reached\n")
        summary = self.memory.get_history_summary()

        if trace_id:
            try:
                db.complete_trace(trace_id, "max_steps", summary, MAX_STEPS, total_tool_calls)
            except Exception:
                pass

        return summary
