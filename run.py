"""
Email Support Agent — Entry Point
==================================
Called by GitHub Actions every 10 minutes.

Priority:
  1. Check Gmail → process unread support emails with Groq LLM + AgentShield
  2. If inbox empty → run one random scenario (keeps AgentShield dashboard live)
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("agent")

AGENTSHIELD_URL     = os.getenv("AGENTSHIELD_URL", "").rstrip("/")
AGENTSHIELD_API_KEY = os.getenv("AGENTSHIELD_API_KEY", "")
GMAIL_ADDRESS       = os.getenv("GMAIL_ADDRESS", "")
GMAIL_APP_PASSWORD  = os.getenv("GMAIL_APP_PASSWORD", "")


# ── AgentShield credential helpers ───────────────────────────────────────────

def _post(path: str, body: dict, token: str = "") -> dict:
    headers: dict = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(
        f"{AGENTSHIELD_URL}/api/v1{path}",
        data=json.dumps(body).encode(),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def provision_credentials() -> str:
    """Auto-provision a tenant+agent on AgentShield. Returns the API key."""
    suffix = str(int(time.time()))[-6:]
    tenant = _post("/tenants", {
        "name": f"Email Agent {suffix}",
        "slug": f"email-agent-{suffix}",
    })
    ag = _post("/agents", {
        "tenant_id": tenant["id"],
        "name": "Email Support Agent",
        "role": "support",
        "scopes": ["read:order", "read:customer", "write:refund", "write:email"],
    })
    api_key: str = ag["api_key"]

    log.info("━" * 60)
    log.info("✅ Provisioned new agent.")
    log.info("   Set AGENTSHIELD_API_KEY = %s", api_key)
    log.info("   (add this as a GitHub Secret to reuse across runs)")
    log.info("━" * 60)

    # Load demo security policy
    try:
        tok = _post("/agents/token", {"api_key": api_key})
        _post(
            f"/policies/load-yaml?tenant_id={tenant['id']}&file_path=policies/demo.yaml",
            {}, token=tok.get("access_token", ""),
        )
        log.info("✅ Demo policy loaded")
    except Exception as e:
        log.warning("Policy load skipped (non-fatal): %s", e)

    return api_key


def resolve_api_key() -> str:
    key = AGENTSHIELD_API_KEY
    if not key:
        log.info("AGENTSHIELD_API_KEY not set — provisioning new agent…")
        for attempt in range(5):
            try:
                return provision_credentials()
            except Exception as exc:
                wait = 15 * (attempt + 1)
                log.warning("Attempt %d failed: %s. Retrying in %ds…", attempt + 1, exc, wait)
                time.sleep(wait)
        log.error("❌ Could not provision credentials. Exiting.")
        sys.exit(1)
    return key


def patch_shield(api_key: str) -> None:
    """
    shield.py reads DEFAULT_API_KEY at module import time.
    Patch the singleton client so @protect uses the correct key.
    """
    os.environ["AGENTSHIELD_API_KEY"] = api_key
    from agent import shield as _s
    _s._default_client.api_key = api_key
    _s._default_client.token   = None  # force fresh JWT fetch


# ── Email mode ────────────────────────────────────────────────────────────────

def run_email_mode() -> int:
    """Read Gmail inbox, process each unread support email. Returns count processed."""
    from agent.email_client import GmailClient
    from agent.email_agent  import EmailSupportAgent

    gmail = GmailClient(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
    try:
        emails = gmail.fetch_unread()
    except Exception as exc:
        log.error("Gmail fetch failed: %s", exc)
        log.error("→ Make sure IMAP is enabled on %s", GMAIL_ADDRESS)
        return 0

    if not emails:
        log.info("📭 No unread support emails")
        return 0

    agent = EmailSupportAgent()

    for mail in emails:
        log.info("─" * 60)
        result = agent.process(mail)
        reply  = result.get("reply", "")
        verdict = result.get("verdict", "?")

        try:
            gmail.send_reply(
                to      = mail.reply_to or mail.from_addr,
                subject = mail.subject,
                body    = reply,
            )
        except Exception as exc:
            log.error("Reply send failed: %s", exc)

        log.info("✔ Processed | verdict=%-6s | to=%s", verdict, mail.from_addr)

    return len(emails)


# ── Scenario fallback mode ────────────────────────────────────────────────────

def run_scenario_mode() -> None:
    """Run one random scenario to keep the AgentShield dashboard alive."""
    from agent.scenarios import pick_scenario
    from agent.shield    import ShieldBlocked, ShieldEscalated
    from agent           import tools

    scenario  = pick_scenario()
    tool_name = scenario["tool"]
    args      = scenario["args"]

    log.info("─" * 60)
    log.info("📋 Inbox empty — scenario fallback: %s", scenario["label"])

    tool_map = {
        "get_customer":        tools.get_customer,
        "search_customer":     tools.search_customer,
        "get_customer_orders": tools.get_customer_orders,
        "issue_refund":        tools.issue_refund,
        "send_email":          tools.send_email,
        "delete_customer":     tools.delete_customer,
    }
    fn = tool_map.get(tool_name)
    if not fn:
        log.warning("Unknown tool: %s", tool_name)
        return

    try:
        fn(**args)
        log.info("✅ ALLOW | tool=%s", tool_name)
    except ShieldBlocked as e:
        log.info("⛔ BLOCK | tool=%s | %s", tool_name, e.reason)
    except ShieldEscalated as e:
        log.info("⚠️  HITL | tool=%s | approval=%s", tool_name, e.approval_id)
    except Exception as exc:
        log.error("❌ Scenario error: %s", exc)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not AGENTSHIELD_URL:
        log.error("AGENTSHIELD_URL is not set. Exiting.")
        sys.exit(1)

    log.info("🛡️  Email Support Agent")
    log.info("   AgentShield : %s", AGENTSHIELD_URL)
    log.info("   Gmail       : %s", GMAIL_ADDRESS or "(not configured)")

    api_key = resolve_api_key()
    patch_shield(api_key)

    if GMAIL_ADDRESS and GMAIL_APP_PASSWORD:
        processed = run_email_mode()
        if processed == 0:
            # No real emails — keep dashboard active with a scenario
            run_scenario_mode()
    else:
        log.info("Gmail not configured — scenario mode only")
        run_scenario_mode()

    log.info("✔ Run complete")


if __name__ == "__main__":
    main()
