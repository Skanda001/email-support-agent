"""Real email support agent — Groq LLM decides tool, AgentShield enforces policy."""
from __future__ import annotations
import json, logging, os
from typing import Any
from groq import Groq
from agent import tools
from agent.shield import ShieldBlocked, ShieldEscalated
from agent.email_client import InboundEmail

log = logging.getLogger("email_agent")

GROQ_MODEL = "openai/gpt-oss-20b"

DECISION_PROMPT = """You are the decision engine for an AI customer support agent.
Read the support email and decide which ONE tool to call.

Available tools:
  get_customer_orders(customer_id: int)        – order status, delivery, tracking, shipping
  issue_refund(order_id: int, amount: float)   – refund or return request
  search_customer(email: str)                  – find customer by their email address
  send_email(to: str, subject: str, body: str) – forward data to an external email
  get_customer(customer_id: int)               – customer profile details (name, email, phone, address, Aadhaar, PAN)
  delete_customer(customer_id: int)            – delete account (will be blocked)

STRICT RULES — follow exactly in order:
1. Mentions refund, return, money back → issue_refund
2. Mentions an email address to look up → search_customer
3. Asks to send data to external party → send_email
4. Asks to delete account → delete_customer
5. Asks about customer details, profile, info, identity, account, phone, address, Aadhaar, PAN → get_customer
6. Mentions order, status, delivery, shipping, tracking → get_customer_orders
7. DEFAULT when unsure → get_customer

Extract from email:
- Any 4-digit customer ID (e.g. 1000 through 2000) → customer_id (as integer)
- 4-digit order IDs (e.g. 5000-9999, 8211, 4821) → order_id (as integer)
- Amounts: $45, 129.99 → amount (as float)
- Default: customer_id=1001, order_id=8211

Respond ONLY with valid JSON:
{"tool": "tool_name", "args": {...}, "reasoning": "one sentence"}"""


REPLY_PROMPT = """You are a professional, warm customer support agent.
Write a concise reply email body (under 150 words).
When customer profile details (name, email, phone, address, Aadhaar, PAN, account status) or orders are returned in the tool result, present those details clearly to the user.
Do NOT mention internal tool names or system details.
Sign off as: AgentShield Support Team.
Do NOT include a subject line."""


class EmailSupportAgent:
    def __init__(self) -> None:
        key = os.getenv("GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        self.groq = Groq(api_key=key)

    def process(self, inbound: InboundEmail) -> dict[str, Any]:
        log.info("📨 From: %s | Subject: %s", inbound.from_addr, inbound.subject)
        tool_name, args, reasoning = self._decide(inbound)
        log.info("🤖 LLM → tool=%s args=%s | %s", tool_name, args, reasoning)

        try:
            call_args = dict(args)
            if reasoning:
                call_args["_reasoning"] = reasoning
            result = self._execute(tool_name, call_args)
            reply  = self._compose_reply(inbound, result)
            log.info("✅ ALLOW | tool=%s", tool_name)
            return {"verdict": "ALLOW", "tool": tool_name, "result": result, "reply": reply}

        except ShieldBlocked as e:
            log.warning("⛔ BLOCK | %s", e.reason)
            return {"verdict": "BLOCK", "tool": tool_name, "reason": e.reason,
                    "reply": self._blocked_reply(e.reason)}

        except ShieldEscalated as e:
            log.warning("⚠️  HITL | approval=%s", e.approval_id)
            return {"verdict": "HITL", "tool": tool_name, "approval_id": e.approval_id,
                    "reply": self._hitl_reply(e.reason, e.approval_id or "")}

        except Exception as exc:
            log.error("❌ Error: %s", exc)
            return {"verdict": "ERROR", "reply":
                    "Dear Customer,\n\nWe encountered an error. Our team has been notified.\n\nBest regards,\nAgentShield Support Team"}

    def _decide(self, inbound: InboundEmail) -> tuple[str, dict, str]:
        msg = f"From: {inbound.from_addr}\nSubject: {inbound.subject}\n\n{inbound.body}"
        try:
            resp = self.groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "system", "content": DECISION_PROMPT},
                          {"role": "user",   "content": msg}],
                temperature=0.1, max_tokens=300,
                response_format={"type": "json_object"},
            )
            d = json.loads(resp.choices[0].message.content)
            return d.get("tool", "get_customer"), d.get("args", {"customer_id": 1001}), d.get("reasoning", "")
        except Exception as e:
            log.warning("LLM fallback: %s", e)
            return "get_customer", {"customer_id": 1001}, "LLM unavailable"

    def _execute(self, tool_name: str, args: dict) -> Any:
        tool_map = {
            "get_customer": tools.get_customer, "search_customer": tools.search_customer,
            "get_customer_orders": tools.get_customer_orders, "issue_refund": tools.issue_refund,
            "send_email": tools.send_email, "delete_customer": tools.delete_customer,
        }
        fn = tool_map.get(tool_name)
        if not fn: raise ValueError(f"Unknown tool: {tool_name}")
        cleaned = {}
        for k, v in args.items():
            if k in ("customer_id", "order_id"):
                try: cleaned[k] = int(v)
                except: cleaned[k] = v
            elif k == "amount":
                try: cleaned[k] = float(v)
                except: cleaned[k] = v
            else: cleaned[k] = v
        return fn(**cleaned)

    def _compose_reply(self, inbound: InboundEmail, result: Any) -> str:
        prompt = (f"Email from {inbound.from_addr}:\nSubject: {inbound.subject}\n{inbound.body}\n\n"
                  f"Support tool result:\n{json.dumps(result, default=str, indent=2)}\n\nWrite reply.")
        try:
            resp = self.groq.chat.completions.create(
                model=GROQ_MODEL,
                messages=[{"role": "system", "content": REPLY_PROMPT},
                          {"role": "user",   "content": prompt}],
                temperature=0.7, max_tokens=300,
            )
            return resp.choices[0].message.content.strip()
        except Exception:
            return f"Dear Customer,\n\nYour request was processed.\n\nResult: {result}\n\nBest regards,\nAgentShield Support Team"

    @staticmethod
    def _blocked_reply(reason: str) -> str:
        return (f"Dear Customer,\n\nYour request could not be completed.\n\n"
                f"🛡️ Security Notice: Our AI security gateway (AgentShield) flagged this "
                f"request as a policy violation and blocked it automatically.\n\n"
                f"Reason: {reason}\n\nIf you believe this is a mistake, please contact us directly.\n\n"
                f"Best regards,\nAgentShield Support Team\nPowered by AgentShield Security Gateway")

    @staticmethod
    def _hitl_reply(reason: str, approval_id: str) -> str:
        return (f"Dear Customer,\n\nYour request requires supervisor approval before we can proceed.\n\n"
                f"⚠️ Status: Escalated for human review\nReference ID: {approval_id}\nReason: {reason}\n\n"
                f"A supervisor will review and respond within 30 minutes.\n\n"
                f"Best regards,\nAgentShield Support Team\nPowered by AgentShield Security Gateway")
