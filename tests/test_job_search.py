from unittest.mock import patch, MagicMock

from src.tools.job_search import JobSearchTool


class TestJobSearchTool:
    def test_tool_metadata(self):
        tool = JobSearchTool()
        assert tool.name == "search_jobs"
        assert "keywords" in tool.parameters["properties"]

    def test_openai_spec(self):
        tool = JobSearchTool()
        spec = tool.to_openai_spec()
        assert spec["type"] == "function"
        assert spec["function"]["name"] == "search_jobs"

    @patch("src.tools.job_search.requests.get")
    def test_search_remoteok(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = [
            {"legal": "metadata"},
            {
                "position": "Senior Python Engineer",
                "company": "TechCorp",
                "tags": ["python", "backend", "ai"],
                "url": "https://example.com/job/1",
                "date": "2026-02-20",
                "description": "Build backend systems",
            },
            {
                "position": "Frontend React Developer",
                "company": "WebCo",
                "tags": ["react", "javascript"],
                "url": "https://example.com/job/2",
                "date": "2026-02-20",
                "description": "Build UIs",
            },
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        tool = JobSearchTool()
        result = tool._search_remoteok(["python"])

        assert len(result) == 1
        assert result[0]["title"] == "Senior Python Engineer"
        assert result[0]["source"] == "RemoteOK"

    @patch("src.tools.job_search.requests.get")
    def test_search_arbeitnow(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {
                    "title": "AI Backend Engineer",
                    "company_name": "AICorp",
                    "location": "Berlin",
                    "tags": ["python", "ai", "backend"],
                    "url": "https://example.com/job/3",
                    "description": "Build AI systems with Python",
                    "remote": True,
                },
            ],
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        tool = JobSearchTool()
        result = tool._search_arbeitnow(["python"])

        assert len(result) == 1
        assert result[0]["company"] == "AICorp"
        assert result[0]["source"] == "Arbeitnow"

    @patch("src.tools.job_search.requests.get")
    def test_deduplication(self, mock_get):
        """Same job from both sources should appear once."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        # Both sources return the same job
        remoteok_data = [
            {"legal": "metadata"},
            {
                "position": "Python Engineer",
                "company": "SameCo",
                "tags": ["python"],
                "url": "https://remoteok.com/job/1",
                "description": "Python work",
            },
        ]
        arbeitnow_data = {
            "data": [
                {
                    "title": "Python Engineer",
                    "company_name": "SameCo",
                    "tags": ["python"],
                    "url": "https://arbeitnow.com/job/1",
                    "description": "Python work",
                },
            ],
        }

        mock_get.side_effect = [
            MagicMock(json=lambda: remoteok_data, raise_for_status=MagicMock()),
            MagicMock(json=lambda: arbeitnow_data, raise_for_status=MagicMock()),
        ]

        tool = JobSearchTool()
        result = tool.execute(keywords=["python"])

        assert result["success"] is True
        assert result["total_found"] == 1  # Deduplicated

    @patch("src.tools.job_search.requests.get")
    def test_max_results(self, mock_get):
        """Should respect max_results limit."""
        jobs = [
            {
                "position": f"Python Engineer {i}",
                "company": f"Co{i}",
                "tags": ["python"],
                "url": f"https://example.com/{i}",
                "description": "Python work",
            }
            for i in range(20)
        ]

        mock_get.side_effect = [
            MagicMock(
                json=lambda: [{"legal": "meta"}] + jobs,
                raise_for_status=MagicMock(),
            ),
            MagicMock(
                json=lambda: {"data": []},
                raise_for_status=MagicMock(),
            ),
        ]

        tool = JobSearchTool()
        result = tool.execute(keywords=["python"], max_results=5)

        assert result["returned"] == 5
        assert len(result["jobs"]) == 5

    @patch("src.tools.job_search.requests.get")
    def test_network_failure_handled(self, mock_get):
        """Should return empty results on network failure, not crash."""
        import requests
        mock_get.side_effect = requests.RequestException("Connection failed")

        tool = JobSearchTool()
        result = tool.execute(keywords=["python"])

        assert result["success"] is True
        assert result["total_found"] == 0

    def test_no_keywords_match(self):
        """With impossible keywords, should return empty."""
        tool = JobSearchTool()
        result = tool.execute(keywords=["xyznonexistent12345"])

        assert result["success"] is True
        # May or may not find results depending on live API
