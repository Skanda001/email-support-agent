"""AgentShield Standalone Python SDK for External Agents.

This SDK is 100% decoupled from the AgentShield gateway core.
External agents use this SDK to enforce Zero-Trust access control
via real HTTP round-trips to the AgentShield gateway API.
"""
from __future__ import annotations

import functools
import inspect
import json
import logging
import os
import urllib.request
import urllib.error
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger("shield.sdk")

def _get_default_gateway_url() -> str:
    if url := os.getenv("AGENTSHIELD_URL"):
        return url.rstrip("/")
    port = os.getenv("PORT", "8000")
    return f"http://127.0.0.1:{port}"

DEFAULT_GATEWAY_URL = _get_default_gateway_url()
DEFAULT_API_KEY = os.getenv("AGENTSHIELD_API_KEY", "ash_wa9sPIWTOIkZFyCMvxXtuir_qBtrMPIRTzuwsxB8xxg")


class ShieldError(Exception):
    """Base class for AgentShield SDK errors."""


@dataclass
class ShieldBlocked(ShieldError):
    """Raised when the AgentShield gateway blocks tool execution."""
    tool: str
    risk_score: float
    reason: str
    audit_id: Optional[str] = None

    def __str__(self) -> str:
        return f"[AgentShield BLOCKED] Tool '{self.tool}' blocked (Risk: {self.risk_score}/100). Reason: {self.reason}"


@dataclass
class ShieldEscalated(ShieldError):
    """Raised when the AgentShield gateway escalates a tool call to Human-in-the-Loop."""
    tool: str
    risk_score: float
    reason: str
    approval_id: Optional[str] = None
    audit_id: Optional[str] = None

    def __str__(self) -> str:
        return (
            f"[AgentShield HITL] Tool '{self.tool}' escalated for supervisor sign-off "
            f"(Approval ID: {self.approval_id}). Reason: {self.reason}"
        )


class ShieldClient:
    """Client for making direct HTTP round-trips to the AgentShield Gateway."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        token: Optional[str] = None,
        direct_handler: Optional[Callable[..., dict[str, Any]]] = None,
    ) -> None:
        self._base_url = base_url
        self.api_key = api_key or DEFAULT_API_KEY
        self.token = token or os.getenv("AGENTSHIELD_TOKEN")
        self.direct_handler = direct_handler
        self.direct_approval_handler: Optional[Callable[..., dict[str, Any]]] = None

    @property
    def base_url(self) -> str:
        if self._base_url:
            return self._base_url.rstrip("/")
        return _get_default_gateway_url()

    @base_url.setter
    def base_url(self, value: Optional[str]) -> None:
        self._base_url = value

    def _ensure_token(self) -> str:
        """Obtain a valid JWT if not already cached."""
        token = self.token or os.getenv("AGENTSHIELD_TOKEN")
        if token:
            self.token = token
            return token

        url = f"{self.base_url}/api/v1/agents/token"
        req_data = json.dumps({"api_key": self.api_key}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                self.token = data.get("access_token")
                return self.token or ""
        except Exception as e:
            logger.warning("Failed to authenticate with AgentShield gateway: %s", e)
            return ""

    def decide(
        self,
        tool: str,
        arguments: dict[str, Any],
        resource_type: Optional[str] = None,
        data_classification: Optional[str] = "internal",
        approval_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Send a tool execution intent to /api/v1/decide and get the gateway verdict."""
        # 1. Direct in-process execution (used when agent is plugged inside AgentShield backend)
        if self.direct_handler:
            try:
                return self.direct_handler(
                    tool=tool,
                    arguments=arguments,
                    resource_type=resource_type,
                    data_classification=data_classification,
                    approval_id=approval_id,
                )
            except Exception as e:
                logger.error("Error in direct handler: %s", e)
                raise ShieldError(f"Error evaluating security decision: {e}")

        # 2. HTTP gateway network request (used when agent is standalone external client)
        token = self._ensure_token()
        url = f"{self.base_url}/api/v1/decide"
        payload = {
            "tool": tool,
            "arguments": arguments,
            "resource_type": resource_type or "unknown",
            "data_classification": data_classification or "internal",
        }
        if approval_id:
            payload["approval_id"] = approval_id
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            err_body = err.read().decode("utf-8")
            try:
                detail = json.loads(err_body).get("detail", err_body)
            except Exception:
                detail = err_body
            if err.code == 403:
                raise ShieldBlocked(
                    tool=tool,
                    risk_score=100.0,
                    reason=f"Gateway rejected access (403): {detail}",
                )
            raise ShieldError(f"HTTP {err.code}: {detail}")
        except Exception as e:
            logger.error("Error communicating with AgentShield gateway: %s", e)
            # FAIL-CLOSED: when the gateway is unreachable, block the tool call.
            # A security gateway must never silently allow actions it cannot evaluate.
            raise ShieldBlocked(
                tool=tool,
                risk_score=100.0,
                reason=f"Gateway unavailable — fail-closed policy activated: {e}",
            )

    def decide_approval(
        self,
        approval_id: str,
        approved: bool = True,
        decided_by: str = "supervisor",
        note: Optional[str] = None,
    ) -> dict[str, Any]:
        """Approve or deny an escalated HITL approval."""
        if self.direct_approval_handler:
            try:
                return self.direct_approval_handler(
                    approval_id=approval_id,
                    approved=approved,
                    decided_by=decided_by,
                    note=note,
                )
            except Exception as e:
                logger.error("Error in direct approval handler: %s", e)
                raise ShieldError(f"Error evaluating approval decision: {e}")

        token = self._ensure_token()
        url = f"{self.base_url}/api/v1/approvals/{approval_id}/decide"
        payload = {
            "approved": approved,
            "decided_by": decided_by,
            "note": note or ("Approved by supervisor via SDK" if approved else "Denied by supervisor"),
        }
        req_data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))


# Global singleton client
_default_client = ShieldClient()


def protect(
    tool: str,
    resource_type: str = "unknown",
    data_classification: str = "internal",
    **extra: Any,
) -> Callable:
    """Decorator for tool functions. Enforces AgentShield security policy over HTTP."""

    def decorator(fn: Callable) -> Callable:
        if inspect.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                res = _default_client.decide(
                    tool=tool,
                    arguments=kwargs,
                    resource_type=resource_type,
                    data_classification=data_classification,
                )
                verdict = res.get("verdict")
                risk_score = res.get("risk_score", 0)
                reasons = res.get("reasons", [])
                reason_str = ", ".join(reasons) if reasons else "Policy evaluation"
                decision_id = str(res.get("decision_id", ""))

                approval_id = str(res.get("approval_id") or decision_id)

                if verdict in ("BLOCK",):
                    raise ShieldBlocked(
                        tool=tool,
                        risk_score=risk_score,
                        reason=reason_str,
                        audit_id=decision_id,
                    )
                if verdict in ("ESCALATE", "HITL"):
                    raise ShieldEscalated(
                        tool=tool,
                        risk_score=risk_score,
                        reason=reason_str,
                        approval_id=approval_id,
                        audit_id=decision_id,
                    )

                call_kwargs = dict(kwargs)
                appr_id = call_kwargs.pop("_shield_approval_id", None)
                reasoning = call_kwargs.pop("_reasoning", None)

                decide_args = dict(call_kwargs)
                if reasoning:
                    decide_args["_reasoning"] = str(reasoning)

                res = await _default_client.decide(
                    tool=tool,
                    arguments=decide_args,
                    resource_type=resource_type,
                    data_classification=data_classification,
                    approval_id=appr_id,
                )
                verdict = res.get("verdict")
                risk_score = res.get("risk_score", 0)
                reasons = res.get("reasons", [])
                reason_str = ", ".join(reasons) if reasons else "Policy evaluation"
                decision_id = str(res.get("decision_id", ""))

                approval_id = str(res.get("approval_id") or decision_id)

                if verdict in ("BLOCK",):
                    raise ShieldBlocked(
                        tool=tool,
                        risk_score=risk_score,
                        reason=reason_str,
                        audit_id=decision_id,
                    )
                if verdict in ("ESCALATE", "HITL"):
                    raise ShieldEscalated(
                        tool=tool,
                        risk_score=risk_score,
                        reason=reason_str,
                        approval_id=approval_id,
                        audit_id=decision_id,
                    )

                # In-flight PII Masking: if gateway masked the arguments, invoke with safe masked data
                if res.get("masked") and isinstance(res.get("masked_arguments"), dict):
                    call_kwargs.update(res["masked_arguments"])

                return await fn(*args, **call_kwargs)

            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                call_kwargs = dict(kwargs)
                appr_id = call_kwargs.pop("_shield_approval_id", None)
                reasoning = call_kwargs.pop("_reasoning", None)

                decide_args = dict(call_kwargs)
                if reasoning:
                    decide_args["_reasoning"] = str(reasoning)

                res = _default_client.decide(
                    tool=tool,
                    arguments=decide_args,
                    resource_type=resource_type,
                    data_classification=data_classification,
                    approval_id=appr_id,
                )
                verdict = res.get("verdict")
                risk_score = res.get("risk_score", 0)
                reasons = res.get("reasons", [])
                reason_str = ", ".join(reasons) if reasons else "Policy evaluation"
                decision_id = str(res.get("decision_id", ""))

                approval_id = str(res.get("approval_id") or decision_id)

                if verdict in ("BLOCK",):
                    raise ShieldBlocked(
                        tool=tool,
                        risk_score=risk_score,
                        reason=reason_str,
                        audit_id=decision_id,
                    )
                if verdict in ("HITL",):
                    raise ShieldEscalated(
                        tool=tool,
                        risk_score=risk_score,
                        reason=reason_str,
                        approval_id=approval_id,
                        audit_id=decision_id,
                    )

                # In-flight PII Masking: if gateway masked the arguments, invoke with safe masked data
                if res.get("masked") and isinstance(res.get("masked_arguments"), dict):
                    call_kwargs.update(res["masked_arguments"])

                return fn(*args, **call_kwargs)

            return sync_wrapper

    return decorator
