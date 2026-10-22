"""Automated test suite for Section 6A: Isolated OpenAI Reasoning Gateway & Policy Enclosure."""
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Tuple

from universal_adaptive_engine.adapters.host_adapter import HostEnvironmentAdapter
from universal_adaptive_engine.providers.gateway import (
    OpenAIReasoningGateway,
    GatewayPolicyDecision,
    GatewaySecurityError,
    GatewayAuditRecord,
)
from universal_adaptive_engine.providers.config import OpenAIConfig
from universal_adaptive_engine.providers.openai_provider import OpenAIReasoningProvider
from universal_adaptive_engine.providers.models import (
    ReasoningRequest,
    ReasoningStatus,
    ReasoningPurpose,
)


class OpenAIGatewayTestCase(unittest.TestCase):
    """Verify Section 6A policy invariants, destination restrictions, and audit logging."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.audit_file = Path(self.temp_dir.name) / "test_gateway_audit.jsonl"
        self.gateway = OpenAIReasoningGateway(audit_file=self.audit_file)

    def tearDown(self):
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Test A: Authorized Destination Test (Section 6A.7.A)
    # -------------------------------------------------------------------------
    def test_authorized_destinations_allowed(self):
        # /v1/responses, /v1/chat/completions, and /v1/models on api.openai.com:443 over HTTPS
        for endpoint in ("/v1/responses", "/v1/chat/completions", "/v1/models"):
            url = f"https://api.openai.com{endpoint}"
            decision, reason = self.gateway.evaluate_request(
                method="POST" if "models" not in endpoint else "GET",
                url=url,
                caller_component="openai_reasoning_gateway",
                verify_tls=True,
            )
            self.assertEqual(decision, GatewayPolicyDecision.ALLOWED, f"Failed on endpoint {endpoint}")
            self.assertIsNone(reason)

    def test_dispatch_authorized_destination_success(self):
        def mock_transport(method, url, headers, payload, timeout):
            return 200, {"id": "resp-123", "output_text": "Reasoning analysis valid"}, {}

        gw = OpenAIReasoningGateway(audit_file=self.audit_file, transport=mock_transport)
        status_code, data, _ = gw.dispatch_request(
            method="POST",
            url="https://api.openai.com/v1/responses",
            headers={"Authorization": "Bearer sk-test-key-123456789"},
            payload={"model": "o3-mini", "input": []},
            caller_component="openai_reasoning_gateway",
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(data["output_text"], "Reasoning analysis valid")

        # Verify audit record was created
        records = gw.get_audit_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["decision"], "ALLOWED")
        self.assertEqual(records[0]["host"], "api.openai.com")
        self.assertEqual(records[0]["endpoint"], "/v1/responses")
        self.assertEqual(records[0]["status_code"], 200)

    # -------------------------------------------------------------------------
    # Test C: Unauthorized Destination & Policy Violation Tests (Section 6A.7.C)
    # -------------------------------------------------------------------------
    def test_unauthorized_hosts_blocked(self):
        unauthorized_hosts = [
            "https://google.com/v1/responses",
            "https://attacker.xyz/v1/responses",
            "https://api.openai.com.evil.com/v1/responses",
            "https://192.168.1.1/v1/responses",
            "https://example.com/v1/chat/completions",
        ]
        for url in unauthorized_hosts:
            with self.assertRaises(GatewaySecurityError) as ctx:
                self.gateway.dispatch_request("POST", url, {}, {})
            self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_HOST)

    def test_insecure_scheme_blocked(self):
        url = "http://api.openai.com/v1/responses"
        with self.assertRaises(GatewaySecurityError) as ctx:
            self.gateway.dispatch_request("POST", url, {}, {})
        self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_INSECURE_SCHEME)

    def test_unauthorized_ports_blocked(self):
        for port in (80, 8080, 8443, 22):
            url = f"https://api.openai.com:{port}/v1/responses"
            with self.assertRaises(GatewaySecurityError) as ctx:
                self.gateway.dispatch_request("POST", url, {}, {})
            self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_PORT)

    def test_unauthorized_endpoints_blocked(self):
        for bad_endpoint in ("/v1/files", "/v1/fine_tuning", "/v1/audio", "/v1/embeddings", "/v1/admin"):
            url = f"https://api.openai.com{bad_endpoint}"
            with self.assertRaises(GatewaySecurityError) as ctx:
                self.gateway.dispatch_request("POST", url, {}, {})
            self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_ENDPOINT)

    def test_tls_verification_bypass_blocked(self):
        url = "https://api.openai.com/v1/responses"
        with self.assertRaises(GatewaySecurityError) as ctx:
            self.gateway.dispatch_request("POST", url, {}, {}, verify_tls=False)
        self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_TLS_VALIDATION_FAILURE)

    def test_http_redirect_disallowed(self):
        # Section 6A.3: Do not permit redirects to secondary or arbitrary destinations
        def mock_redirect_transport(method, url, headers, payload, timeout):
            return 302, {}, {"Location": "https://attacker.com/steal"}

        gw = OpenAIReasoningGateway(audit_file=self.audit_file, transport=mock_redirect_transport)
        with self.assertRaises(GatewaySecurityError) as ctx:
            gw.dispatch_request("POST", "https://api.openai.com/v1/responses", {}, {})
        self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_REDIRECT_ATTEMPT)

    # -------------------------------------------------------------------------
    # Test D: Component Isolation Tests (Section 6A.7.D)
    # -------------------------------------------------------------------------
    def test_component_isolation_in_gateway(self):
        # If an unauthorized component tries to call the gateway directly
        for bad_component in ("contract_scanner", "shell_worker", "fuzzer", "arbitrary_agent"):
            with self.assertRaises(GatewaySecurityError) as ctx:
                self.gateway.dispatch_request(
                    method="POST",
                    url="https://api.openai.com/v1/responses",
                    headers={},
                    caller_component=bad_component,
                )
            self.assertEqual(ctx.exception.decision, GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_COMPONENT)

    def test_host_adapter_component_level_enforcement(self):
        adapter = HostEnvironmentAdapter(Path("/home/nova/projects/cantina"))

        # 1. Designated reasoning gateway component: PROCEED
        valid_reasoning_contract = {
            "task_id": "TASK-OAI-GW-01",
            "component": "openai_reasoning_gateway",
            "destination": "api.openai.com:443",
            "permissions_required": ["network.outbound.openai_reasoning_gateway"],
        }
        res_valid = adapter.validate_contract(valid_reasoning_contract)
        self.assertTrue(res_valid["valid"])
        self.assertEqual(res_valid["recommendation"], "PROCEED")

        # 2. Smart-contract scanner attempting to use reasoning exception: REJECT
        scanner_contract = {
            "task_id": "TASK-SCAN-01",
            "component": "smart_contract_scanner",
            "destination": "api.openai.com:443",
            "permissions_required": ["network.outbound.openai_reasoning_gateway"],
        }
        res_scanner = adapter.validate_contract(scanner_contract)
        self.assertFalse(res_scanner["valid"])
        self.assertEqual(res_scanner["recommendation"], "REJECT_OR_ADAPT")
        self.assertTrue(any("restricted exclusively" in iss for iss in res_scanner["issues"]))

        # 3. Shell worker attempting to use reasoning exception: REJECT
        shell_contract = {
            "task_id": "TASK-SHELL-01",
            "component": "shell_execution_worker",
            "destination": "api.openai.com:443",
            "permissions_required": ["network.outbound.openai_reasoning_gateway"],
        }
        res_shell = adapter.validate_contract(shell_contract)
        self.assertFalse(res_shell["valid"])
        self.assertEqual(res_shell["recommendation"], "REJECT_OR_ADAPT")

        # 4. Gateway attempting to reach unauthorized destination: REJECT
        unauthorized_dest_contract = {
            "task_id": "TASK-OAI-GW-02",
            "component": "openai_reasoning_gateway",
            "destination": "evil.com:443",
            "permissions_required": ["network.outbound.openai_reasoning_gateway"],
        }
        res_bad_dest = adapter.validate_contract(unauthorized_dest_contract)
        self.assertFalse(res_bad_dest["valid"])
        self.assertTrue(any("unauthorized" in iss for iss in res_bad_dest["issues"]))

    # -------------------------------------------------------------------------
    # Test E: Credential Isolation Test (Section 6A.7.E)
    # -------------------------------------------------------------------------
    def test_credential_isolation_in_audit_logs(self):
        secret_key = "sk-proj-super-secret-production-token-12345"

        def mock_transport(method, url, headers, payload, timeout):
            return 200, {"choices": [{"message": {"content": "ok"}}]}, {}

        gw = OpenAIReasoningGateway(audit_file=self.audit_file, transport=mock_transport)
        gw.dispatch_request(
            method="POST",
            url="https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {secret_key}"},
            payload={"test": "data"},
            caller_component="openai_reasoning_gateway",
        )

        audit_content = self.audit_file.read_text(encoding="utf-8")
        self.assertNotIn(secret_key, audit_content)
        self.assertNotIn("Bearer", audit_content)

    # -------------------------------------------------------------------------
    # Test F: Policy-Regression Test (Section 6A.7.F)
    # -------------------------------------------------------------------------
    def test_policy_regression_default_deny_preserved(self):
        adapter = HostEnvironmentAdapter(Path("/home/nova/projects/cantina"))

        # General network.outbound MUST remain strictly blocked
        general_net_contract = {
            "task_id": "TASK-NET-GEN",
            "permissions_required": ["network.outbound"],
        }
        res_gen = adapter.validate_contract(general_net_contract)
        self.assertFalse(res_gen["valid"])
        self.assertEqual(res_gen["recommendation"], "REJECT_OR_ADAPT")

        # Arbitrary network permissions MUST also be blocked
        for perm in ("network.http", "network.rpc", "network.websocket", "network.general"):
            c = {"task_id": f"TASK-{perm}", "permissions_required": [perm]}
            res = adapter.validate_contract(c)
            self.assertFalse(res["valid"])

    # -------------------------------------------------------------------------
    # Test G: Application Integration Test (Section 6A.7.G)
    # -------------------------------------------------------------------------
    def test_provider_routes_through_gateway_for_responses_api(self):
        captured_urls = []

        def mock_transport(method, url, headers, payload, timeout):
            captured_urls.append(url)
            return 200, {
                "id": "resp-test-responses",
                "output_text": "Structured reasoning plan generated via Responses API",
                "usage": {"total_tokens": 42},
            }, {}

        cfg = OpenAIConfig(
            api_key="sk-test-key",
            model="o3-mini",
            api_mode="responses",
            audit_file=str(self.audit_file),
        )
        provider = OpenAIReasoningProvider(config=cfg, transport=mock_transport)
        req = ReasoningRequest(instructions="Plan audit", purpose=ReasoningPurpose.PLANNING)
        resp = provider.reason(req)

        self.assertEqual(resp.status, ReasoningStatus.SUCCESS)
        self.assertIn("Responses API", resp.output_text)
        self.assertEqual(len(captured_urls), 1)
        self.assertTrue(captured_urls[0].endswith("/v1/responses"))

        # Check audit record created via gateway
        records = provider.gateway.get_audit_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["endpoint"], "/v1/responses")
        self.assertEqual(records[0]["decision"], "ALLOWED")

    def test_provider_handles_gateway_security_rejection_safely(self):
        # Configure an unauthorized base_url on the provider
        cfg = OpenAIConfig(
            api_key="sk-test-key",
            model="o3-mini",
            base_url="https://unauthorized-proxy.com/v1",
            audit_file=str(self.audit_file),
        )
        provider = OpenAIReasoningProvider(config=cfg)
        req = ReasoningRequest(instructions="Analyze code", purpose=ReasoningPurpose.SECURITY_ASSISTANCE)
        resp = provider.reason(req)

        # Provider must fail safely without throwing unhandled exceptions or fabricating success
        self.assertIn(resp.status, (ReasoningStatus.PROVIDER_UNAVAILABLE, ReasoningStatus.FAILED))
        self.assertTrue(any("unauthorized" in err.lower() for err in resp.errors))


if __name__ == "__main__":
    unittest.main()
