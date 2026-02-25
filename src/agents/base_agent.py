import json
import os
from abc import ABC, abstractmethod

from openai import OpenAI
from dotenv import load_dotenv

from ..memory import AgentMemory, AgentStep, ToolResult
from ..tools.base import ToolRegistry

load_dotenv()

MAX_STEPS = 10

# Provider configurations
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
        provider: str = "groq",
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
            api_key = os.getenv(self._provider_config["env_key"])
            base_url = self._provider_config["base_url"]
            self._client = OpenAI(api_key=api_key, base_url=base_url)
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

    def _build_tool_descriptions(self) -> str:
        lines = []
        for tool in self.registry.list_tools():
            lines.append(f"- **{tool.name}**: {tool.description}")
        return "\n".join(lines)

    def _build_messages(self, task: str) -> list[dict]:
        """Build message history for the LLM call."""
        prompt = self.system_prompt.format(
            tool_descriptions=self._build_tool_descriptions()
        )
        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": task},
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

    def run(self, task: str) -> str:
        """Execute the agent's ReAct loop on a given task."""
        self.memory.clear()
        print(f"\n--- {self.name.upper()} AGENT ---\n")

        for step_num in range(1, MAX_STEPS + 1):
            print(f"  [{self.name}] Step {step_num}/{MAX_STEPS}")

            messages = self._build_messages(task)
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

                result = self._execute_tool(func_name, func_args)
                observation = json.dumps(result, indent=2)

                print(f"    Result: {'OK' if result.get('success') else 'FAILED'}")

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
            else:
                content = message.content or ""
                if "FINAL_ANSWER" in content:
                    final = content.split("FINAL_ANSWER", 1)[1].strip()
                    print(f"  [{self.name}] Complete ({step_num} steps)\n")
                    return final

                self.memory.add_step(AgentStep(
                    step_number=step_num,
                    thought=content,
                ))
                print(f"    Thought: {content[:150]}")

        print(f"  [{self.name}] Max steps reached\n")
        return self.memory.get_history_summary()
