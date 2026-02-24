import json
import os

from dotenv import load_dotenv
from openai import OpenAI

from .memory import AgentMemory, AgentStep, ToolResult
from .prompts import SYSTEM_PROMPT, TASK_PROMPT
from .tools.base import ToolRegistry

load_dotenv()

MAX_STEPS = 10


class Agent:
    """ReAct agent that reasons, acts, and observes in a loop.

    This is the core runtime engine. On each step:
      1. The LLM receives the full context (system prompt + history + task)
      2. It decides whether to call a tool or produce a final answer
      3. If it calls a tool, we execute it and feed the result back
      4. The loop continues until FINAL_ANSWER or max steps reached

    The LLM runs at runtime making autonomous decisions — this is
    agentic AI, not just AI-assisted code generation.
    """

    def __init__(self, registry: ToolRegistry, model: str = "gpt-4o-mini"):
        self.registry = registry
        self.model = model
        self.memory = AgentMemory()
        self._client = None

    @property
    def client(self):
        """Lazy-initialize the OpenAI client so it's only created when needed."""
        if self._client is None:
            self._client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        return self._client

    @client.setter
    def client(self, value):
        """Allow injecting a mock client for testing."""
        self._client = value

    def _build_system_prompt(self) -> str:
        """Construct the system prompt with available tool descriptions."""
        tool_lines = []
        for tool in self.registry.list_tools():
            tool_lines.append(f"- **{tool.name}**: {tool.description}")
        tool_descriptions = "\n".join(tool_lines)
        return SYSTEM_PROMPT.format(tool_descriptions=tool_descriptions)

    def _build_messages(self, task: str) -> list[dict]:
        """Build the full message history for the LLM call.
        Includes system prompt, task, and all previous steps."""
        messages = [
            {"role": "system", "content": self._build_system_prompt()},
            {"role": "user", "content": task},
        ]

        # Replay the reasoning history so the LLM has full context
        for step in self.memory.steps:
            # The agent's thought
            messages.append({
                "role": "assistant",
                "content": f"Thought: {step.thought}",
            })
            # If a tool was called, include the call and result
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
        """Look up and execute a tool from the registry."""
        tool = self.registry.get(name)
        if tool is None:
            return {"success": False, "error": f"Unknown tool: {name}"}
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return {"success": False, "error": f"Tool execution failed: {str(e)}"}

    def run(self, jd_source: str, resume_path: str, is_url: bool = False) -> str:
        """Execute the full agent loop for a job application analysis.

        Returns the final analysis text after the agent has completed
        its multi-step reasoning process.
        """
        self.memory.clear()

        additional = ""
        if is_url:
            additional = "The JD source is a URL — use is_url=true when parsing."

        task = TASK_PROMPT.format(
            jd_source=jd_source,
            resume_path=resume_path,
            additional_context=additional,
        )

        print("\n--- Agent Starting ---\n")

        for step_num in range(1, MAX_STEPS + 1):
            print(f"Step {step_num}/{MAX_STEPS}")

            messages = self._build_messages(task)

            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self.registry.to_openai_specs(),
                tool_choice="auto",
            )

            message = response.choices[0].message

            # Check if the agent wants to call a tool
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                func_name = tool_call.function.name
                func_args = json.loads(tool_call.function.arguments)

                thought = message.content or f"I need to use {func_name}"
                print(f"  Thought: {thought}")
                print(f"  Action: {func_name}({json.dumps(func_args, indent=2)})")

                result = self._execute_tool(func_name, func_args)
                observation = json.dumps(result, indent=2)

                success = result.get("success", False)
                print(f"  Result: {'OK' if success else 'FAILED'}")

                step = AgentStep(
                    step_number=step_num,
                    thought=thought,
                    tool_call=ToolResult(
                        tool_name=func_name,
                        arguments=func_args,
                        result=result,
                    ),
                    observation=observation,
                )
                self.memory.add_step(step)

            else:
                # No tool call — the agent is providing its final answer
                content = message.content or ""

                if "FINAL_ANSWER" in content:
                    final = content.split("FINAL_ANSWER", 1)[1].strip()
                    print(f"\n--- Agent Complete ({step_num} steps) ---\n")
                    return final

                # Agent gave a thought without a tool call — record and continue
                step = AgentStep(
                    step_number=step_num,
                    thought=content,
                )
                self.memory.add_step(step)
                print(f"  Thought: {content[:200]}")

        print(f"\n--- Agent reached max steps ({MAX_STEPS}) ---\n")
        # Return whatever context we've gathered
        return self.memory.get_history_summary()
