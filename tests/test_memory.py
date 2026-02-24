from src.memory import AgentMemory, AgentStep, ToolResult


class TestAgentMemory:
    def test_empty_memory(self):
        memory = AgentMemory()
        assert memory.step_count == 0
        assert memory.get_history_summary() == "No previous steps."

    def test_add_step(self):
        memory = AgentMemory()
        step = AgentStep(
            step_number=1,
            thought="I need to parse the job description first",
        )
        memory.add_step(step)

        assert memory.step_count == 1
        assert memory.steps[0].thought == "I need to parse the job description first"

    def test_step_with_tool_call(self):
        memory = AgentMemory()
        step = AgentStep(
            step_number=1,
            thought="Let me parse the JD",
            tool_call=ToolResult(
                tool_name="parse_job_description",
                arguments={"source": "some JD text"},
                result={"success": True, "raw_text": "parsed"},
            ),
            observation='{"success": true}',
        )
        memory.add_step(step)

        assert memory.steps[0].tool_call.tool_name == "parse_job_description"
        assert memory.steps[0].tool_call.result["success"] is True

    def test_fact_storage(self):
        memory = AgentMemory()
        memory.store_fact("company_name", "Acme Corp")
        memory.store_fact("role", "Engineer")

        assert memory.get_fact("company_name") == "Acme Corp"
        assert memory.get_fact("role") == "Engineer"
        assert memory.get_fact("nonexistent") is None

    def test_get_all_facts(self):
        memory = AgentMemory()
        memory.store_fact("a", 1)
        memory.store_fact("b", 2)

        facts = memory.get_all_facts()
        assert facts == {"a": 1, "b": 2}

    def test_history_summary(self):
        memory = AgentMemory()
        memory.add_step(AgentStep(
            step_number=1,
            thought="Analyzing the JD",
            tool_call=ToolResult(
                tool_name="parse_job_description",
                arguments={"source": "text"},
                result={"success": True},
            ),
            observation="Parsed successfully",
        ))
        memory.add_step(AgentStep(
            step_number=2,
            thought="Now checking resume",
        ))

        summary = memory.get_history_summary()
        assert "Step 1:" in summary
        assert "parse_job_description" in summary
        assert "Step 2:" in summary
        assert "Now checking resume" in summary

    def test_clear(self):
        memory = AgentMemory()
        memory.add_step(AgentStep(step_number=1, thought="test"))
        memory.store_fact("key", "value")

        memory.clear()

        assert memory.step_count == 0
        assert memory.get_fact("key") is None

    def test_tool_result_has_timestamp(self):
        result = ToolResult(
            tool_name="test",
            arguments={},
            result={"success": True},
        )
        assert result.timestamp is not None
        assert "T" in result.timestamp  # ISO format
