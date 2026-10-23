"""Unit and integration tests for OpenAI Reasoning Provider in USAP."""
import json
import os
import unittest
from typing import Any, Tuple
from unittest.mock import MagicMock, patch

from universal_adaptive_engine.providers.protocol import ReasoningProvider
from universal_adaptive_engine.providers.models import (
    ReasoningStatus,
    ReasoningPurpose,
    ReasoningRequest,
    ReasoningResponse,
    ProviderCapabilities,
    ProviderHealth,
)
from universal_adaptive_engine.providers.config import (
    OpenAIConfig,
    redact_api_key,
    REASONING_MODELS,
    SUPPORTED_REASONING_EFFORTS,
)
from universal_adaptive_engine.providers.openai_provider import OpenAIReasoningProvider, _default_requests_transport
from universal_adaptive_engine.providers.factory import (
    get_reasoning_provider,
    list_available_providers,
)
from universal_adaptive_engine.harness.orchestrator import UniversalAdaptiveOrchestrator


class OpenAIConfigTestCase(unittest.TestCase):
    """Verify configuration validation, env loading, and secret redaction."""

    def test_config_defaults(self):
        cfg = OpenAIConfig(api_key="sk-test-secret-1234567890abcdef")
        self.assertEqual(cfg.model, "o3-mini")
        self.assertEqual(cfg.reasoning_effort, "high")
        self.assertEqual(cfg.timeout_seconds, 60.0)
        self.assertEqual(cfg.max_retries, 2)
        self.assertFalse(cfg.store_responses)
        self.assertEqual(cfg.fallback_provider, "none")

    def test_config_validation_invalid_model(self):
        with self.assertRaises(ValueError):
            OpenAIConfig(api_key="sk-test", model="")

    def test_config_validation_negative_timeout(self):
        with self.assertRaises(ValueError):
            OpenAIConfig(api_key="sk-test", timeout_seconds=-5.0)

    def test_config_validation_negative_retries(self):
        with self.assertRaises(ValueError):
            OpenAIConfig(api_key="sk-test", max_retries=-1)

    def test_config_reasoning_effort_validation(self):
        # Valid reasoning efforts on reasoning models
        for effort in ("low", "medium", "high"):
            cfg = OpenAIConfig(api_key="sk-test", model="o3-mini", reasoning_effort=effort)
            self.assertEqual(cfg.reasoning_effort, effort)

        # Invalid reasoning effort
        with self.assertRaises(ValueError):
            OpenAIConfig(api_key="sk-test", model="o3-mini", reasoning_effort="maximum")

    def test_config_reasoning_effort_on_non_reasoning_model(self):
        # gpt-4o does not support reasoning_effort
        with self.assertRaises(ValueError):
            OpenAIConfig(api_key="sk-test", model="gpt-4o", reasoning_effort="high")

        # But gpt-4o without reasoning_effort is valid
        cfg = OpenAIConfig(api_key="sk-test", model="gpt-4o", reasoning_effort=None)
        self.assertIsNone(cfg.reasoning_effort)

    def test_from_env_loading(self):
        fake_env = {
            "OPENAI_API_KEY": "sk-proj-testkey1234567890abcdef",
            "OPENAI_MODEL": "o1-mini",
            "OPENAI_REASONING_EFFORT": "medium",
            "OPENAI_TIMEOUT_SECONDS": "45",
            "OPENAI_MAX_RETRIES": "3",
            "OPENAI_STORE_RESPONSES": "true",
            "USAP_OPENAI_FALLBACK_PROVIDER": "none",
        }
        cfg = OpenAIConfig.from_env(fake_env)
        self.assertEqual(cfg.api_key, "sk-proj-testkey1234567890abcdef")
        self.assertEqual(cfg.model, "o1-mini")
        self.assertEqual(cfg.reasoning_effort, "medium")
        self.assertEqual(cfg.timeout_seconds, 45.0)
        self.assertEqual(cfg.max_retries, 3)
        self.assertTrue(cfg.store_responses)
        self.assertEqual(cfg.fallback_provider, "none")

    def test_from_env_dotenv_file(self):
        import tempfile
        from pathlib import Path
        from universal_adaptive_engine.providers.config import load_dotenv_dict

        with tempfile.TemporaryDirectory() as tmpdir:
            env_file = Path(tmpdir) / ".env"
            env_file.write_text("OPENAI_API_KEY=sk-test-from-dotenv-file-12345\nOPENAI_MODEL=gpt-4o\n# Comment\n", encoding="utf-8")
            loaded = load_dotenv_dict(env_file)
            self.assertEqual(loaded.get("OPENAI_API_KEY"), "sk-test-from-dotenv-file-12345")
            self.assertEqual(loaded.get("OPENAI_MODEL"), "gpt-4o")

    def test_from_env_non_reasoning_model_drops_effort(self):
        fake_env = {
            "OPENAI_API_KEY": "sk-proj-testkey",
            "OPENAI_MODEL": "gpt-4o-mini",
            "OPENAI_REASONING_EFFORT": "high",
        }
        cfg = OpenAIConfig.from_env(fake_env)
        self.assertEqual(cfg.model, "gpt-4o-mini")
        self.assertIsNone(cfg.reasoning_effort)

    def test_redact_api_key(self):
        self.assertEqual(redact_api_key(None), "<UNSET>")
        self.assertEqual(redact_api_key(""), "<UNSET>")
        self.assertEqual(redact_api_key("short"), "[REDACTED]")
        full_key = "sk-proj-1234567890abcdef1234567890"
        redacted = redact_api_key(full_key)
        self.assertTrue(redacted.startswith("sk-proj"))
        self.assertTrue(redacted.endswith("7890"))
        self.assertIn("[REDACTED]", redacted)
        self.assertNotIn("1234567890abcdef", redacted)

    def test_to_safe_dict(self):
        cfg = OpenAIConfig(api_key="sk-proj-1234567890abcdef1234567890", model="o3-mini")
        safe = cfg.to_safe_dict()
        self.assertNotIn("sk-proj-1234567890abcdef1234567890", str(safe))
        self.assertTrue(safe["api_key_configured"])
        self.assertIn("[REDACTED]", safe["api_key_redacted"])


class OpenAIProviderMockedTestCase(unittest.TestCase):
    """Test OpenAIReasoningProvider behaviors using mocked transport."""

    def setUp(self):
        self.fake_key = "sk-proj-mock-key-for-testing-123456"
        self.config = OpenAIConfig(
            api_key=self.fake_key,
            model="o3-mini",
            reasoning_effort="high",
            timeout_seconds=10.0,
            max_retries=2,
        )

    def test_protocol_conformance(self):
        provider = OpenAIReasoningProvider(config=self.config)
        self.assertIsInstance(provider, ReasoningProvider)

    def test_capabilities(self):
        provider = OpenAIReasoningProvider(config=self.config)
        caps = provider.get_capabilities()
        self.assertEqual(caps.provider_name, "openai")
        self.assertTrue(caps.supports_reasoning)
        self.assertTrue(caps.supports_structured_output)
        self.assertIn("o3-mini", caps.supported_models)
        self.assertIn("high", caps.reasoning_efforts)

    def test_health_check_unconfigured(self):
        provider = OpenAIReasoningProvider(config=OpenAIConfig(api_key=None))
        health = provider.health_check()
        self.assertEqual(health.status, "UNAVAILABLE")
        self.assertIn("not configured", health.error or "")

    def test_health_check_healthy(self):
        def mock_transport(method, url, headers, payload, timeout):
            return 200, {"data": [{"id": "o3-mini"}]}, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        health = provider.health_check()
        self.assertEqual(health.status, "HEALTHY")
        self.assertIsNotNone(health.latency_ms)

    def test_health_check_unhealthy(self):
        def mock_transport(method, url, headers, payload, timeout):
            return 401, {"error": {"message": "Invalid API key"}}, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        health = provider.health_check()
        self.assertEqual(health.status, "UNHEALTHY")
        self.assertIn("Invalid API key", health.error or "")

    def test_default_health_check_probes_provider_instead_of_trusting_configuration(self):
        provider = OpenAIReasoningProvider(config=self.config)
        calls = []

        def unavailable_probe(**kwargs):
            calls.append(kwargs)
            return 503, {"error": {"message": "temporarily unavailable"}}, {}

        provider.gateway.dispatch_request = unavailable_probe
        health = provider.health_check()
        self.assertEqual(health.status, "UNHEALTHY")
        self.assertEqual(len(calls), 1)
        self.assertTrue(calls[0]["url"].endswith("/v1/models"))

    def test_default_transport_exposes_redirects_to_gateway_for_rejection(self):
        response = MagicMock(status_code=302, headers={"Location": "https://example.invalid/"}, text="")
        response.json.return_value = {}
        request = MagicMock(return_value=response)
        with patch.dict("sys.modules", {"requests": MagicMock(request=request)}):
            status, _, _ = _default_requests_transport(
                "POST", "https://api.openai.com/v1/responses", {"Authorization": "Bearer test"}, {"input": "test"}, 1.0
            )
        self.assertEqual(status, 302)
        self.assertFalse(request.call_args.kwargs["allow_redirects"])

    def test_successful_reasoning_chat_completions(self):
        captured_payloads = []

        def mock_transport(method, url, headers, payload, timeout):
            captured_payloads.append(payload)
            data = {
                "id": "chatcmpl-test-123",
                "model": "o3-mini",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "Analysis: The withdrawal proof check enforces invariant INV-DISPUTE-01.",
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {
                    "prompt_tokens": 50,
                    "completion_tokens": 25,
                    "total_tokens": 75,
                    "completion_tokens_details": {"reasoning_tokens": 15},
                },
            }
            return 200, data, {}

        chat_config = OpenAIConfig(
            api_key=self.fake_key,
            model="o3-mini",
            reasoning_effort="high",
            timeout_seconds=10.0,
            max_retries=2,
            api_mode="chat_completions",
        )
        provider = OpenAIReasoningProvider(config=chat_config, transport=mock_transport)
        req = ReasoningRequest(
            prompt="Analyze dispute finalization invariant",
            purpose=ReasoningPurpose.SECURITY_ANALYSIS,
            context={"contract": "DisputeGame", "function": "proveWithdrawal"},
            system_instruction="You are a smart contract security expert.",
        )

        resp = provider.reason(req)
        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertIn("INV-DISPUTE-01", resp.content)
        self.assertEqual(resp.model, "o3-mini")
        self.assertEqual(resp.usage["total_tokens"], 75)
        self.assertEqual(resp.usage["reasoning_tokens"], 15)

        # Inspect sent payload
        sent = captured_payloads[0]
        self.assertEqual(sent["model"], "o3-mini")
        self.assertEqual(sent["reasoning_effort"], "high")
        # System instruction and context included
        content_blobs = [m["content"] for m in sent["messages"]]
        self.assertTrue(any("smart contract security expert" in c for c in content_blobs))
        self.assertTrue(any("DisputeGame" in c for c in content_blobs))

    def test_successful_reasoning_responses_api(self):
        captured_payloads = []

        def mock_transport(method, url, headers, payload, timeout):
            captured_payloads.append(payload)
            data = {
                "id": "resp-test-123",
                "model": "o3-mini",
                "output_text": "Analysis: Responses API confirmed invariant INV-DISPUTE-01.",
                "usage": {
                    "input_tokens": 50,
                    "output_tokens": 25,
                    "total_tokens": 75,
                },
            }
            return 200, data, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(
            prompt="Analyze dispute finalization invariant",
            purpose=ReasoningPurpose.SECURITY_ANALYSIS,
        )

        resp = provider.reason(req)
        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertIn("INV-DISPUTE-01", resp.content)

        sent = captured_payloads[0]
        self.assertEqual(sent["model"], "o3-mini")
        self.assertEqual(sent["reasoning"], {"effort": "high"})
        self.assertIn("input", sent)

    def test_responses_api_output_array_parsing(self):
        def mock_transport(method, url, headers, payload, timeout):
            data = {
                "id": "resp-test-456",
                "model": "o3-mini",
                "output": [
                    {
                        "type": "reasoning",
                        "summary": [{"type": "summary_text", "text": "Reasoned about withdrawal delay."}],
                    },
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": [
                            {"type": "output_text", "text": "Final Analysis: Invariant INV-DELAYED-WETH-02 verified."}
                        ],
                    },
                ],
                "usage": {
                    "input_tokens": 80,
                    "output_tokens": 40,
                    "total_tokens": 120,
                },
            }
            return 200, data, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Check delayed WETH invariant")
        resp = provider.reason(req)
        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertIn("INV-DELAYED-WETH-02", resp.content)
        self.assertEqual(resp.usage["total_tokens"], 120)

    def test_cancel_response(self):
        called_url = []

        def mock_transport(method, url, headers, payload, timeout):
            called_url.append((method, url))
            return 200, {"id": "resp-789", "status": "cancelled"}, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        ok, res = provider.cancel_response("resp-789")
        self.assertTrue(ok)
        self.assertEqual(res["status"], "cancelled")
        self.assertEqual(called_url[0][0], "POST")
        self.assertIn("/v1/responses/resp-789/cancel", called_url[0][1])

    def test_successful_structured_output_clean_json(self):
        structured_json = {
            "hypothesis": "Reentrancy in delayed unlock",
            "likelihood": "LOW",
            "suggested_check": "Verify nonReentrant modifier on DelayedWETH.unlock",
        }

        def mock_transport(method, url, headers, payload, timeout):
            data = {
                "id": "chatcmpl-test-structured",
                "model": "o3-mini",
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(structured_json),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 40},
            }
            return 200, data, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(
            prompt="Generate hypothesis for DelayedWETH",
            purpose=ReasoningPurpose.HYPOTHESIS_GENERATION,
            structured_schema={
                "type": "object",
                "properties": {
                    "hypothesis": {"type": "string"},
                    "likelihood": {"type": "string"},
                },
            },
        )
        resp = provider.reason_structured(req)
        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertEqual(resp.structured_output["hypothesis"], "Reentrancy in delayed unlock")
        self.assertEqual(resp.structured_output["likelihood"], "LOW")

    def test_structured_output_markdown_fenced_json(self):
        fenced_content = "```json\n{\"plan\": [\"step 1\", \"step 2\"]}\n```"

        def mock_transport(method, url, headers, payload, timeout):
            data = {
                "choices": [
                    {
                        "message": {"content": fenced_content},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 30},
            }
            return 200, data, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Produce plan", purpose=ReasoningPurpose.PLANNING)
        resp = provider.reason_structured(req)
        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertEqual(resp.structured_output, {"plan": ["step 1", "step 2"]})

    def test_structured_output_invalid_json(self):
        def mock_transport(method, url, headers, payload, timeout):
            data = {
                "choices": [
                    {
                        "message": {"content": "This is raw unstructured prose without JSON."},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"total_tokens": 10},
            }
            return 200, data, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Produce json", purpose=ReasoningPurpose.PLANNING)
        resp = provider.reason_structured(req)
        self.assertEqual(resp.status, ReasoningStatus.FAILED)
        self.assertIn("Failed to parse", resp.error_message or "")

    def test_error_auth_failure_401_no_retry(self):
        attempt_count = 0

        def mock_transport(method, url, headers, payload, timeout):
            nonlocal attempt_count
            attempt_count += 1
            return 401, {"error": {"message": "Incorrect API key provided"}}, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Test auth fail")
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.AUTH_FAILURE)
        self.assertEqual(attempt_count, 1)  # Must fail immediately without retrying
        self.assertIn("Incorrect API key", resp.error_message or "")

    def test_error_rate_limit_429_eventual_success(self):
        calls = 0

        def mock_transport(method, url, headers, payload, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                return 429, {"error": {"message": "Rate limit exceeded"}}, {"retry-after": "0"}
            return 200, {"choices": [{"message": {"content": "Success after retry"}}]}, {"usage": {}}

        # Set max_retries=2
        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Test retry")
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertEqual(resp.content, "Success after retry")
        self.assertEqual(calls, 2)

    def test_error_rate_limit_429_exhaustion(self):
        calls = 0

        def mock_transport(method, url, headers, payload, timeout):
            nonlocal calls
            calls += 1
            return 429, {"error": {"message": "Rate limit reached"}}, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Test retry exhaustion")
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.RATE_LIMITED)
        # initial attempt (1) + max_retries (2) = 3 calls
        self.assertEqual(calls, 3)
        self.assertIn("Rate limit reached", resp.error_message or "")

    def test_error_server_500_exhaustion(self):
        calls = 0

        def mock_transport(method, url, headers, payload, timeout):
            nonlocal calls
            calls += 1
            return 500, {"error": {"message": "Internal server error"}}, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Test server error")
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.PROVIDER_ERROR)
        self.assertEqual(calls, 3)

    def test_error_timeout_exhaustion(self):
        calls = 0

        def mock_transport(method, url, headers, payload, timeout):
            nonlocal calls
            calls += 1
            raise TimeoutError("HTTP request timed out")

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Test timeout")
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.TIMEOUT)
        self.assertEqual(calls, 3)
        self.assertIn("timed out", resp.error_message or "")

    def test_model_refusal(self):
        def mock_transport(method, url, headers, payload, timeout):
            data = {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "refusal": "I cannot fulfill this request due to safety policy.",
                        },
                        "finish_reason": "refusal",
                    }
                ]
            }
            return 200, data, {}

        provider = OpenAIReasoningProvider(config=self.config, transport=mock_transport)
        req = ReasoningRequest(prompt="Test refusal")
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.REFUSAL)
        self.assertIn("refusal", resp.error_message or "")
        self.assertIn("safety policy", resp.error_message or "")

    def test_secret_sanitization_in_errors(self):
        secret = "sk-proj-super-secret-key-that-must-never-leak"
        cfg = OpenAIConfig(api_key=secret)

        def mock_transport(method, url, headers, payload, timeout):
            raise Exception(f"Connection failed while sending authorization header Bearer {secret}")

        provider = OpenAIReasoningProvider(config=cfg, transport=mock_transport)
        resp = provider.reason(ReasoningRequest(prompt="Test sanitize"))

        self.assertIn(resp.status, (ReasoningStatus.FAILED, ReasoningStatus.PROVIDER_UNAVAILABLE))
        self.assertNotIn(secret, resp.error_message or "")
        self.assertIn("[REDACTED]", resp.error_message or "")


class OrchestratorReasoningIntegrationTestCase(unittest.TestCase):
    """Verify UniversalAdaptiveOrchestrator integration with ReasoningProvider."""

    def test_orchestrator_routes_reasoning_and_retains_authority(self):
        def mock_transport(method, url, headers, payload, timeout):
            data = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps({
                                "subtasks": [
                                    {
                                        "task_id": "TASK-1",
                                        "goal": "Inspect scope.md",
                                        "acceptance_criteria": ["Scope matches"],
                                        "dependencies": []
                                    }
                                ],
                                "rationale": "Decomposed per scope requirements"
                            })
                        }
                    }
                ],
                "usage": {"total_tokens": 50},
            }
            return 200, data, {}

        cfg = OpenAIConfig(api_key="sk-test-mock-key-1234567890", model="o3-mini")
        provider = OpenAIReasoningProvider(config=cfg, transport=mock_transport)

        orchestrator = UniversalAdaptiveOrchestrator(
            workspace_root="/home/nova/projects/cantina",
            reasoning_provider=provider,
        )

        req = ReasoningRequest(
            prompt="Plan investigation for dispute portal",
            purpose=ReasoningPurpose.PLANNING,
        )
        resp = orchestrator.reason(req)
        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)

        # Plan with reasoning helper
        plan_res = orchestrator.plan_with_reasoning("Investigate dispute finalization monotonicity")
        self.assertEqual(plan_res["status"], "REASONING_PROPOSAL_GENERATED")
        self.assertEqual(plan_res["authority"], "LOCAL_PLATFORM_RETAINS_EXECUTION_GATE")
        self.assertIn("Inspect scope.md", str(plan_res["proposals"]))


class FactoryTestCase(unittest.TestCase):
    """Verify provider factory mechanics."""

    def test_get_reasoning_provider_openai(self):
        cfg = OpenAIConfig(api_key="sk-test", model="o3-mini")
        p = get_reasoning_provider("openai", config=cfg)
        self.assertIsInstance(p, OpenAIReasoningProvider)

    def test_get_unknown_provider(self):
        with self.assertRaises(ValueError):
            get_reasoning_provider("unknown_provider_xyz")

    def test_list_available_providers(self):
        provs = list_available_providers()
        self.assertIn("openai", provs)


if __name__ == "__main__":
    unittest.main()
