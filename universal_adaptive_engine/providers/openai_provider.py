"""OpenAI Reasoning Provider implementation conforming to USAP architecture."""
from __future__ import annotations
import json
import logging
import os
import time
import uuid
from typing import Any, Callable, Optional

from universal_adaptive_engine.providers.models import (
    ReasoningRequest,
    ReasoningResponse,
    ReasoningStatus,
    ReasoningPurpose,
    ProviderCapabilities,
    ProviderHealth,
)
from universal_adaptive_engine.providers.config import (
    OpenAIConfig,
    REASONING_MODELS,
    redact_api_key,
)
from universal_adaptive_engine.providers.gateway import (
    OpenAIReasoningGateway,
    GatewaySecurityError,
)

logger = logging.getLogger("universal_adaptive_engine.providers.openai")

# Type alias for HTTP transport callable:
# (method, url, headers, payload, timeout) -> (status_code, response_data, response_headers)
HttpTransport = Callable[[str, str, dict[str, str], dict[str, Any], float], tuple[int, dict[str, Any], dict[str, str]]]


def _default_requests_transport(
    method: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> tuple[int, dict[str, Any], dict[str, str]]:
    """Default HTTP transport using requests (or urllib fallback)."""
    try:
        import requests
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=payload,
            timeout=timeout,
            verify=True,
            allow_redirects=False,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"raw_text": resp.text}
        return resp.status_code, data, dict(resp.headers)
    except ImportError:
        import urllib.request
        import urllib.error

        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, response_headers, newurl):
                return None

        req = urllib.request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method=method,
        )
        try:
            opener = urllib.request.build_opener(NoRedirectHandler())
            with opener.open(req, timeout=timeout) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body), dict(response.headers)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            try:
                err_data = json.loads(err_body)
            except Exception:
                err_data = {"error": err_body}
            return e.code, err_data, dict(e.headers)
        except Exception as e:
            return 599, {"error": str(e)}, {}


class OpenAIReasoningProvider:
    """Production-grade OpenAI Reasoning Provider.

    Executes structured reasoning tasks via OpenAI's Responses and Chat Completions API
    with strict isolation, exponential backoff retries, and comprehensive error taxonomy.
    """

    provider_name: str = "openai"

    def __init__(
        self,
        config: Optional[OpenAIConfig] = None,
        transport: Optional[HttpTransport] = None,
    ):
        self.config = config or OpenAIConfig.from_env()
        self.transport = transport or _default_requests_transport
        self.gateway = OpenAIReasoningGateway(
            audit_file=self.config.audit_file,
            transport=self.transport,
        )

    def get_capabilities(self) -> ProviderCapabilities:
        """Return the declared capabilities of this provider."""
        is_reasoning = any(self.config.model.startswith(m) for m in REASONING_MODELS)
        return ProviderCapabilities(
            provider_name=self.provider_name,
            supported_models=(
                "o3-mini", "o1", "o1-mini", "o1-preview", "gpt-4o", "gpt-4o-mini"
            ),
            supports_reasoning_effort=is_reasoning,
            supports_structured_outputs=True,
            supports_response_storage=True,
            supports_streaming=False,
        )

    def health_check(self) -> ProviderHealth:
        """Verify API configuration and readiness without leaking secrets."""
        t0 = time.time()
        if not self.config.api_key:
            return ProviderHealth(
                provider=self.provider_name,
                status="UNAVAILABLE",
                model=self.config.model,
                error="OPENAI_API_KEY is not configured",
            )
        try:
            self.config.validate()
            base = self.config.base_url.rstrip("/")
            models_url = f"{base}/models" if base.endswith("/v1") else f"{base}/v1/models"
            status_code, data, _ = self.gateway.dispatch_request(
                method="GET",
                url=models_url,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                payload=None,
                timeout=min(self.config.timeout_seconds, 5.0),
                caller_component=self.gateway.GATEWAY_COMPONENT_NAME,
            )
            latency_ms = (time.time() - t0) * 1000
            if status_code == 200:
                return ProviderHealth(
                    provider=self.provider_name,
                    status="HEALTHY",
                    model=self.config.model,
                    latency_ms=round(latency_ms, 2),
                )
            err_msg = self._extract_error_message(data) if isinstance(data, dict) else f"HTTP {status_code}"
            return ProviderHealth(
                provider=self.provider_name,
                status="UNHEALTHY",
                model=self.config.model,
                latency_ms=round(latency_ms, 2),
                error=err_msg,
            )
        except Exception as e:
            return ProviderHealth(
                provider=self.provider_name,
                status="UNHEALTHY",
                model=self.config.model,
                latency_ms=round((time.time() - t0) * 1000, 2),
                error=self._sanitize_error(str(e)),
            )

    def reason(self, request: ReasoningRequest) -> ReasoningResponse:
        """Execute a general reasoning query."""
        request.validate()
        return self._execute_reasoning(request, structured_schema=request.output_schema)

    def reason_structured(
        self,
        request: ReasoningRequest,
        schema: Optional[dict[str, Any]] = None,
    ) -> ReasoningResponse:
        """Execute a structured reasoning query conforming to a JSON schema."""
        request.validate()
        target_schema = schema if schema is not None else (request.output_schema if request.output_schema is not None else {})
        return self._execute_reasoning(request, structured_schema=target_schema)

    def cancel_response(self, response_id: str) -> tuple[bool, dict[str, Any]]:
        """Cancel an ongoing response using POST /v1/responses/{response_id}/cancel."""
        if not response_id or not response_id.strip():
            return False, {"error": "Invalid response_id"}
        base = self.config.base_url.rstrip("/")
        cancel_url = f"{base}/responses/{response_id.strip()}/cancel" if base.endswith("/v1") else f"{base}/v1/responses/{response_id.strip()}/cancel"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "USAP-UniversalAdaptiveEngine/1.2.0",
        }
        status_code, data, _ = self.gateway.dispatch_request(
            method="POST",
            url=cancel_url,
            headers=headers,
            payload=None,
            timeout=min(self.config.timeout_seconds, 10.0),
            caller_component=self.gateway.GATEWAY_COMPONENT_NAME,
        )
        return status_code == 200, data

    def _execute_reasoning(
        self,
        request: ReasoningRequest,
        structured_schema: Optional[dict[str, Any]],
    ) -> ReasoningResponse:
        t0 = time.time()
        request_id = f"REQ-{uuid.uuid4().hex[:8]}"

        if not self.config.api_key:
            return self._handle_failure(
                request=request,
                request_id=request_id,
                status=ReasoningStatus.AUTHENTICATION_FAILED,
                error_msg="OPENAI_API_KEY is missing. Provider cannot execute live request.",
                latency_ms=(time.time() - t0) * 1000,
            )

        payload = self._build_api_payload(request, structured_schema)
        base = self.config.base_url.rstrip("/")
        if self.config.api_mode == "responses":
            endpoint = "/responses" if base.endswith("/v1") else "/v1/responses"
        else:
            endpoint = "/chat/completions" if base.endswith("/v1") else "/v1/chat/completions"
        url = f"{base}{endpoint}"

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "USAP-UniversalAdaptiveEngine/1.2.0",
        }

        retries = 0
        last_error = ""
        last_status_code = 0
        last_status = ReasoningStatus.FAILED

        while retries <= self.config.max_retries:
            try:
                status_code, data, resp_headers = self.gateway.dispatch_request(
                    method="POST",
                    url=url,
                    headers=headers,
                    payload=payload,
                    timeout=self.config.timeout_seconds,
                    request_id=request_id,
                    caller_component=self.gateway.GATEWAY_COMPONENT_NAME,
                )
                last_status_code = status_code

                if status_code == 200:
                    latency_ms = (time.time() - t0) * 1000
                    return self._parse_success_response(
                        request=request,
                        request_id=request_id,
                        data=data,
                        latency_ms=latency_ms,
                        is_structured=structured_schema is not None,
                    )

                # Classify HTTP Error
                last_error = self._extract_error_message(data)

                # Non-retryable errors: fail immediately
                if status_code in (400, 401, 403):
                    reasoning_status = (
                        ReasoningStatus.AUTHENTICATION_FAILED
                        if status_code in (401, 403)
                        else ReasoningStatus.FAILED
                    )
                    return self._handle_failure(
                        request=request,
                        request_id=request_id,
                        status=reasoning_status,
                        error_msg=f"HTTP {status_code}: {last_error}",
                        latency_ms=(time.time() - t0) * 1000,
                    )

                # Retryable errors: 429, 500, 502, 503, 504
                if status_code == 429:
                    last_status = ReasoningStatus.RATE_LIMITED
                elif status_code >= 500:
                    last_status = ReasoningStatus.PROVIDER_UNAVAILABLE
                else:
                    last_status = ReasoningStatus.FAILED

                retries += 1
                if retries <= self.config.max_retries:
                    # Exponential backoff
                    backoff = 0.2 * (2 ** (retries - 1))
                    time.sleep(backoff)

            except Exception as exc:
                exc_str = str(exc).lower()
                exc_name = type(exc).__name__.lower()
                last_error = self._sanitize_error(str(exc))
                if isinstance(exc, TimeoutError) or "timed out" in exc_str or "timeout" in exc_str or "timeout" in exc_name:
                    last_status = ReasoningStatus.TIMEOUT
                else:
                    last_status = ReasoningStatus.PROVIDER_UNAVAILABLE

                retries += 1
                if retries <= self.config.max_retries:
                    backoff = 0.2 * (2 ** (retries - 1))
                    time.sleep(backoff)

        # Retries exhausted
        latency_ms = (time.time() - t0) * 1000
        return self._handle_failure(
            request=request,
            request_id=request_id,
            status=last_status,
            error_msg=f"Exhausted {self.config.max_retries} retries. Last error: {last_error}",
            latency_ms=latency_ms,
        )

    def _build_api_payload(
        self,
        request: ReasoningRequest,
        structured_schema: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """Construct standard OpenAI payload adhering strictly to model limits."""
        messages: list[dict[str, str]] = []

        # System/developer prompt with safety boundaries
        system_instruction = request.context_metadata.get("system_instruction")
        extra_sys = f"\nSystem Instruction:\n{system_instruction}" if system_instruction else ""
        system_content = (
            f"You are the Primary Reasoning Engine for the Universal Smart-contract Adaptive Platform (USAP).\n"
            f"Task Purpose: {request.purpose.value if isinstance(request.purpose, ReasoningPurpose) else str(request.purpose)}\n"
            f"Core Invariant: You provide analytical rationale, decomposition, and candidate recommendations only. "
            f"You have no authority to grant execution permissions, bypass local safety policies, or mutate state.\n"
            f"Instructions:\n{request.instructions}{extra_sys}"
        )
        # For o-series models, system message is typically developer or system role
        messages.append({"role": "system", "content": system_content})

        # User message with input, target context, and evidence references
        user_parts = []
        if request.input_data:
            if isinstance(request.input_data, (dict, list)):
                user_parts.append(f"Input Data:\n```json\n{json.dumps(request.input_data, indent=2)}\n```")
            else:
                user_parts.append(f"Input Data:\n{request.input_data}")

        if request.target_context:
            user_parts.append(f"Target Context:\n```json\n{json.dumps(request.target_context, indent=2)}\n```")

        if request.evidence_refs:
            user_parts.append(f"Referenced Evidence: {', '.join(request.evidence_refs)}")

        user_content = "\n\n".join(user_parts) if user_parts else "Analyze the task based on the system instructions."
        messages.append({"role": "user", "content": user_content})

        effective_model = request.model_override or self.config.model
        payload: dict[str, Any] = {
            "model": effective_model,
        }
        if self.config.api_mode == "responses":
            payload["instructions"] = system_content
            payload["input"] = [{"role": "user", "content": user_content}]
        else:
            payload["messages"] = messages

        # Apply reasoning effort only if supported
        is_reasoning = any(effective_model.startswith(m) for m in REASONING_MODELS)
        if is_reasoning and self.config.reasoning_effort:
            if self.config.api_mode == "responses":
                payload["reasoning"] = {"effort": self.config.reasoning_effort}
            else:
                payload["reasoning_effort"] = self.config.reasoning_effort

        # Output tokens limit
        if self.config.max_output_tokens:
            if self.config.api_mode == "responses":
                payload["max_output_tokens"] = self.config.max_output_tokens
            else:
                payload["max_completion_tokens"] = self.config.max_output_tokens

        # Store response policy
        payload["store"] = self.config.store_responses

        # Structured schema injection
        if structured_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "usap_structured_reasoning",
                    "strict": True,
                    "schema": structured_schema,
                },
            }

        return payload

    def _parse_success_response(
        self,
        request: ReasoningRequest,
        request_id: str,
        data: dict[str, Any],
        latency_ms: float,
        is_structured: bool,
    ) -> ReasoningResponse:
        """Parse completed response and extract usage, text, and structured data."""
        response_id = data.get("id")
        choices = data.get("choices", [])
        content = ""
        msg = {}
        finish_reason = "stop"

        # Check error object from Responses API
        if "error" in data and isinstance(data["error"], dict) and data["error"].get("message"):
            err_msg = data["error"]["message"]
            return self._handle_failure(
                request=request,
                request_id=request_id,
                status=ReasoningStatus.FAILED,
                error_msg=f"OpenAI error: {err_msg}",
                latency_ms=latency_ms,
            )

        reasoning_summary = ""
        if "output_text" in data and isinstance(data["output_text"], str):
            content = data["output_text"]
        elif choices:
            choice = choices[0]
            finish_reason = choice.get("finish_reason", "stop")
            msg = choice.get("message", {})
            content = msg.get("content", "")
        elif "output" in data and isinstance(data["output"], list) and len(data["output"]) > 0:
            extracted_text_parts = []
            for item in data["output"]:
                if not isinstance(item, dict):
                    continue
                item_type = item.get("type")
                if item_type == "message" or item.get("role") == "assistant":
                    c = item.get("content", [])
                    if isinstance(c, list):
                        for c_item in c:
                            if isinstance(c_item, dict) and c_item.get("type") == "output_text":
                                extracted_text_parts.append(c_item.get("text", ""))
                            elif isinstance(c_item, str):
                                extracted_text_parts.append(c_item)
                    elif isinstance(c, str):
                        extracted_text_parts.append(c)
                elif item_type == "reasoning":
                    for s in item.get("summary", []):
                        if isinstance(s, dict) and "text" in s:
                            reasoning_summary = s["text"]
            content = "\n".join(extracted_text_parts) if extracted_text_parts else (data.get("output_text") or "")
        else:
            return self._handle_failure(
                request=request,
                request_id=request_id,
                status=ReasoningStatus.FAILED,
                error_msg="Malformed response: neither choices nor output_text present",
                latency_ms=latency_ms,
            )

        incomplete_reason = (data.get("incomplete_details") or {}).get("reason")
        if incomplete_reason:
            finish_reason = incomplete_reason

        # Check for model refusal
        refusal_reason = msg.get("refusal") or data.get("refusal")
        if refusal_reason or finish_reason == "content_filter":
            refusal_text = f"Model refusal: {refusal_reason or 'Model refused request due to content filters'}"
            return ReasoningResponse(
                provider=self.provider_name,
                model=self.config.model,
                status=ReasoningStatus.REFUSED,
                request_id=request_id,
                response_id=response_id,
                output_text=refusal_text,
                rationale_summary=refusal_text,
                latency_ms=round(latency_ms, 2),
                errors=[refusal_text],
            )

        # Parse usage (supporting both Chat and Responses API conventions)
        raw_usage = data.get("usage", {})
        prompt_tokens = raw_usage.get("prompt_tokens") or raw_usage.get("input_tokens") or 0
        completion_tokens = raw_usage.get("completion_tokens") or raw_usage.get("output_tokens") or 0
        total_tokens = raw_usage.get("total_tokens") or (prompt_tokens + completion_tokens)
        usage = {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }
        if "completion_tokens_details" in raw_usage:
            details = raw_usage["completion_tokens_details"]
            if "reasoning_tokens" in details:
                usage["reasoning_tokens"] = details["reasoning_tokens"]
        elif "output_tokens_details" in raw_usage:
            details = raw_usage["output_tokens_details"]
            if "reasoning_tokens" in details:
                usage["reasoning_tokens"] = details["reasoning_tokens"]

        structured_dict: Optional[dict[str, Any]] = None
        if is_structured and content:
            clean_json = content.strip()
            if clean_json.startswith("```"):
                lines = clean_json.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                clean_json = "\n".join(lines).strip()
            try:
                structured_dict = json.loads(clean_json)
            except json.JSONDecodeError as e:
                return self._handle_failure(
                    request=request,
                    request_id=request_id,
                    status=ReasoningStatus.FAILED,
                    error_msg=f"Failed to parse structured JSON output: {str(e)}",
                    latency_ms=latency_ms,
                )

        rationale = content[:200] + "..." if len(content) > 200 else content

        return ReasoningResponse(
            provider=self.provider_name,
            model=self.config.model,
            status=ReasoningStatus.SUCCESS,
            output_text=content,
            structured_output=structured_dict,
            request_id=request_id,
            response_id=response_id,
            rationale_summary=rationale,
            evidence_refs=list(request.evidence_refs),
            usage=usage,
            latency_ms=round(latency_ms, 2),
            errors=[],
        )

    def _extract_error_message(self, data: dict[str, Any]) -> str:
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                return self._sanitize_error(err.get("message", str(err)))
            if err:
                return self._sanitize_error(str(err))
            if "raw_text" in data:
                return self._sanitize_error(data["raw_text"][:200])
        return self._sanitize_error(str(data)[:200])

    def _sanitize_error(self, err_str: str) -> str:
        """Strip sensitive credentials from error messages."""
        if self.config.api_key:
            err_str = err_str.replace(self.config.api_key, redact_api_key(self.config.api_key))
        # Mask any other potential sk- keys
        import re
        return re.sub(r"sk-[a-zA-Z0-9_-]{20,}", "[REDACTED_API_KEY]", err_str)

    def _handle_failure(
        self,
        request: ReasoningRequest,
        request_id: str,
        status: ReasoningStatus,
        error_msg: str,
        latency_ms: float,
    ) -> ReasoningResponse:
        sanitized_msg = self._sanitize_error(error_msg)

        # Check for configured fallback provider
        if self.config.fallback_provider and self.config.fallback_provider != "none":
            # Explicitly identify fallback in response
            return ReasoningResponse(
                provider=f"fallback:{self.config.fallback_provider}",
                model="local-rule-heuristic",
                status=ReasoningStatus.SUCCESS,
                output_text=f"Fallback rationale generated locally due to OpenAI failure: {sanitized_msg}",
                structured_output={"fallback": True, "reason": sanitized_msg},
                request_id=request_id,
                rationale_summary=f"Executed via fallback {self.config.fallback_provider}",
                latency_ms=round(latency_ms, 2),
                errors=[f"Primary provider failed: {sanitized_msg}"],
            )

        return ReasoningResponse(
            provider=self.provider_name,
            model=self.config.model,
            status=status,
            output_text="",
            structured_output=None,
            request_id=request_id,
            rationale_summary="",
            latency_ms=round(latency_ms, 2),
            errors=[sanitized_msg],
        )
