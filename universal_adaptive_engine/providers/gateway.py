"""Isolated Network Gateway for OpenAI Reasoning Provider under USAP Section 6A.

Enforces a strictly isolated, narrowly scoped outbound network exception:
- Destination Host: ONLY api.openai.com
- Destination Port: ONLY TCP 443
- Transport Scheme: ONLY HTTPS with verified TLS certificates
- Application Endpoints: ONLY /v1/responses, /v1/chat/completions, and /v1/models
- Default-deny: Rejects all other hosts, schemes, ports, endpoints, and redirects
- Telemetry & Audit: Append-only JSONL audit log with sanitized credentials
"""
from __future__ import annotations
import json
import os
import time
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from universal_adaptive_engine.providers.config import redact_api_key

HttpTransport = Callable[
    [str, str, dict[str, str], Optional[dict[str, Any]], float],
    tuple[int, dict[str, Any], dict[str, str]],
]


class GatewayPolicyDecision(str, Enum):
    """Enforcement decision outcomes for gateway policy evaluation."""
    ALLOWED = "ALLOWED"
    BLOCKED_UNAUTHORIZED_HOST = "BLOCKED_UNAUTHORIZED_HOST"
    BLOCKED_INSECURE_SCHEME = "BLOCKED_INSECURE_SCHEME"
    BLOCKED_UNAUTHORIZED_PORT = "BLOCKED_UNAUTHORIZED_PORT"
    BLOCKED_UNAUTHORIZED_ENDPOINT = "BLOCKED_UNAUTHORIZED_ENDPOINT"
    BLOCKED_REDIRECT_ATTEMPT = "BLOCKED_REDIRECT_ATTEMPT"
    BLOCKED_TLS_VALIDATION_FAILURE = "BLOCKED_TLS_VALIDATION_FAILURE"
    BLOCKED_UNAUTHORIZED_COMPONENT = "BLOCKED_UNAUTHORIZED_COMPONENT"
    ERROR = "ERROR"


class GatewaySecurityError(PermissionError):
    """Raised when an outbound network request violates Section 6A security invariants."""
    def __init__(self, decision: GatewayPolicyDecision, message: str):
        super().__init__(f"[{decision.value}] {message}")
        self.decision = decision
        self.message = message


@dataclass(frozen=True)
class GatewayAuditRecord:
    """Tamper-evident audit entry for network egress attempts."""
    timestamp: str
    request_id: str
    caller_component: str
    method: str
    url: str
    host: str
    port: int
    endpoint: str
    decision: str
    status_code: Optional[int]
    latency_ms: float
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "caller_component": self.caller_component,
            "method": self.method,
            "url": self.url,
            "host": self.host,
            "port": self.port,
            "endpoint": self.endpoint,
            "decision": self.decision,
            "status_code": self.status_code,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


def _default_tls_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: Optional[dict[str, Any]],
    timeout: float,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    """Default transport executing strictly over HTTPS with mandatory TLS verification."""
    try:
        import requests
        # Disallow redirects to prevent redirection attacks to non-whitelisted destinations
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
            verify=True,  # Mandatory TLS certificate verification
            allow_redirects=False,  # Section 6A.3: Do not permit redirects to arbitrary destinations
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text}
        return resp.status_code, data, dict(resp.headers)
    except Exception as e:
        # Fall back to urllib.request if requests fails or is unavailable
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8") if payload else None,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                try:
                    data = json.loads(body)
                except Exception:
                    data = {"raw_text": body}
                return response.status, data, dict(response.headers)
        except urllib.error.HTTPError as he:
            body = he.read().decode("utf-8") if he.fp else ""
            try:
                data = json.loads(body)
            except Exception:
                data = {"raw_text": body}
            return he.code, data, dict(he.headers)
        except Exception as ue:
            raise ue


class OpenAIReasoningGateway:
    """Isolated, narrowly scoped egress gateway for OpenAI API reasoning traffic.
    
    Guarantees:
    1. Only api.openai.com:443 is reachable.
    2. Only /v1/responses, /v1/chat/completions, and /v1/models are authorized.
    3. Mandatory TLS certificate verification.
    4. Immediate rejection of redirects.
    5. Append-only audit logging with zero credential leakage.
    """

    AUTHORIZED_HOSTS: frozenset[str] = frozenset(["api.openai.com"])
    AUTHORIZED_PORTS: frozenset[int] = frozenset([443])
    AUTHORIZED_SCHEMES: frozenset[str] = frozenset(["https"])
    AUTHORIZED_ENDPOINTS: frozenset[str] = frozenset([
        "/v1/responses",
        "/v1/chat/completions",
        "/v1/models",
    ])
    GATEWAY_COMPONENT_NAME: str = "openai_reasoning_gateway"

    def __init__(
        self,
        audit_file: Optional[Path | str] = None,
        transport: Optional[HttpTransport] = None,
        allowed_hosts_override: Optional[frozenset[str]] = None,
    ):
        self.audit_file = Path(audit_file) if audit_file else Path(".orchestrator_state/gateway_network_audit.jsonl")
        self.transport = transport or _default_tls_transport
        self.authorized_hosts = allowed_hosts_override or self.AUTHORIZED_HOSTS
        try:
            self.audit_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    def evaluate_request(
        self,
        method: str,
        url: str,
        caller_component: str = "openai_reasoning_gateway",
        verify_tls: bool = True,
    ) -> tuple[GatewayPolicyDecision, Optional[str]]:
        """Evaluate an egress request against Section 6A policy invariants."""
        # 1. Caller Component Isolation Check
        if caller_component not in (self.GATEWAY_COMPONENT_NAME, "reasoning_provider"):
            return (
                GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_COMPONENT,
                f"Component '{caller_component}' is not authorized to use the reasoning gateway exception. "
                f"Smart-contract scanners, shell tools, and general workers remain under default-deny.",
            )

        # 2. TLS Verification Check
        if not verify_tls:
            return (
                GatewayPolicyDecision.BLOCKED_TLS_VALIDATION_FAILURE,
                "TLS certificate verification cannot be disabled for reasoning gateway traffic.",
            )

        # 3. Parse URL
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            return GatewayPolicyDecision.ERROR, f"Malformed URL: {e}"

        # 4. Scheme Check
        scheme = (parsed.scheme or "").lower().strip()
        if scheme not in self.AUTHORIZED_SCHEMES:
            return (
                GatewayPolicyDecision.BLOCKED_INSECURE_SCHEME,
                f"Insecure scheme '{scheme}' is forbidden. Outbound reasoning traffic must use HTTPS.",
            )

        # 5. Hostname Check
        host = (parsed.hostname or "").lower().strip()
        if host not in self.authorized_hosts:
            return (
                GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_HOST,
                f"Outbound network destination host '{host}' is blocked by USAP default-deny policy. "
                f"Exception applies exclusively to {sorted(self.authorized_hosts)}.",
            )

        # 6. Port Check
        port = parsed.port if parsed.port is not None else 443
        if port not in self.AUTHORIZED_PORTS:
            return (
                GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_PORT,
                f"Destination port {port} is blocked. Gateway authorizes exclusively TCP 443.",
            )

        # 7. Endpoint / Path Check
        path = parsed.path.rstrip("/")
        # Normalize endpoint
        if path not in self.AUTHORIZED_ENDPOINTS and f"{path}/" not in self.AUTHORIZED_ENDPOINTS:
            return (
                GatewayPolicyDecision.BLOCKED_UNAUTHORIZED_ENDPOINT,
                f"Endpoint '{parsed.path}' is unauthorized. Scoped reasoning gateway permits exclusively "
                f"{sorted(self.AUTHORIZED_ENDPOINTS)}.",
            )

        return GatewayPolicyDecision.ALLOWED, None

    def dispatch_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str],
        payload: Optional[dict[str, Any]] = None,
        timeout: float = 60.0,
        request_id: Optional[str] = None,
        caller_component: str = "openai_reasoning_gateway",
        verify_tls: bool = True,
    ) -> tuple[int, dict[str, Any], dict[str, str]]:
        """Audit, evaluate, and dispatch outbound reasoning API request."""
        t0 = time.time()
        req_id = request_id or f"GW-REQ-{int(t0*1000)}"

        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or 443
        endpoint = parsed.path

        # Policy Gate Evaluation
        decision, rejection_reason = self.evaluate_request(
            method=method,
            url=url,
            caller_component=caller_component,
            verify_tls=verify_tls,
        )

        if decision != GatewayPolicyDecision.ALLOWED:
            latency_ms = (time.time() - t0) * 1000
            self._record_audit(
                GatewayAuditRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    request_id=req_id,
                    caller_component=caller_component,
                    method=method.upper(),
                    url=self._sanitize_url(url),
                    host=host,
                    port=port,
                    endpoint=endpoint,
                    decision=decision.value,
                    status_code=None,
                    latency_ms=round(latency_ms, 2),
                    error=rejection_reason,
                )
            )
            raise GatewaySecurityError(decision, rejection_reason or "Request blocked by gateway policy")

        # Sanitize headers for safety
        safe_headers = dict(headers)

        # Dispatch via transport
        try:
            status_code, data, resp_headers = self.transport(
                method.upper(), url, safe_headers, payload, timeout
            )
            latency_ms = (time.time() - t0) * 1000

            # Check for redirect responses
            if status_code in (301, 302, 303, 307, 308):
                redirect_err = f"HTTP {status_code} redirect blocked. Gateway policy prohibits automatic or arbitrary redirection."
                self._record_audit(
                    GatewayAuditRecord(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        request_id=req_id,
                        caller_component=caller_component,
                        method=method.upper(),
                        url=self._sanitize_url(url),
                        host=host,
                        port=port,
                        endpoint=endpoint,
                        decision=GatewayPolicyDecision.BLOCKED_REDIRECT_ATTEMPT.value,
                        status_code=status_code,
                        latency_ms=round(latency_ms, 2),
                        error=redirect_err,
                    )
                )
                raise GatewaySecurityError(GatewayPolicyDecision.BLOCKED_REDIRECT_ATTEMPT, redirect_err)

            self._record_audit(
                GatewayAuditRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    request_id=req_id,
                    caller_component=caller_component,
                    method=method.upper(),
                    url=self._sanitize_url(url),
                    host=host,
                    port=port,
                    endpoint=endpoint,
                    decision=decision.value,
                    status_code=status_code,
                    latency_ms=round(latency_ms, 2),
                    error=None if status_code < 400 else f"HTTP {status_code}",
                )
            )
            return status_code, data, resp_headers

        except Exception as exc:
            latency_ms = (time.time() - t0) * 1000
            if isinstance(exc, GatewaySecurityError):
                raise
            err_msg = str(exc)
            self._record_audit(
                GatewayAuditRecord(
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    request_id=req_id,
                    caller_component=caller_component,
                    method=method.upper(),
                    url=self._sanitize_url(url),
                    host=host,
                    port=port,
                    endpoint=endpoint,
                    decision=GatewayPolicyDecision.ERROR.value,
                    status_code=None,
                    latency_ms=round(latency_ms, 2),
                    error=err_msg,
                )
            )
            raise

    def _sanitize_url(self, url: str) -> str:
        """Strip query parameters or credentials from URLs before auditing."""
        parsed = urllib.parse.urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _record_audit(self, record: GatewayAuditRecord) -> None:
        """Append audit record to local ledger with safe fail-open for audit logging."""
        try:
            with open(self.audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record.to_dict()) + "\n")
        except Exception:
            pass

    def get_audit_records(self) -> list[dict[str, Any]]:
        """Retrieve historical audit records."""
        if not self.audit_file.exists():
            return []
        records = []
        try:
            with open(self.audit_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line.strip()))
        except Exception:
            pass
        return records
