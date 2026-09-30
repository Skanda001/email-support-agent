# Autonomous Email Support Agent 🤖✉️

> **Production AI Customer Support Agent powered by Groq LLM & protected by [AgentShield](https://github.com/Skanda001/agentshield) Zero-Trust Security Gateway.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Groq](https://img.shields.io/badge/Groq-gpt--oss--20b-F55036?style=flat&logo=groq&logoColor=white)](https://groq.com/)
[![AgentShield](https://img.shields.io/badge/Security-AgentShield%20Zero--Trust-009688?style=flat)](https://github.com/Skanda001/agentshield)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## 📌 Overview

This is an autonomous customer support agent that monitors an email inbox (Gmail IMAP), extracts intent, reasons over business actions using **Groq LLM**, and executes database tools.

To prevent rogue behavior, data exfiltration, or prompt injections, all tool calls are wrapped with AgentShield's `@protect` Zero-Trust decorator. AgentShield inspects each tool invocation via HTTP, enforcing PII masking, injection defense, and human approvals before any action touches CRM data.

```
Incoming Email (IMAP) ──► Groq LLM Decision Engine ──► @protect Decorator ──► AgentShield Gateway
                                                             │                        │
                                                             │                        ▼
                                                       ALLOW │               Inspects: PII, Injection,
                                                             ▼               Rules, Kill-Switch
                                                     Local Tool Executes              │
                                                     (CRM / Order / Refund)           ▼
                                                             │               Decision: ALLOW / BLOCK / HITL
                                                             ▼
                                                    Customer Reply (SMTP)
```

---

## 🌟 Key Capabilities

* **Groq AI Tool Calling & Reasoning**: Uses high-speed LLM inference (`openai/gpt-oss-20b`) to classify inbound support tickets, parse customer IDs, and invoke appropriate tools with explicit reasoning strings.
* **Zero-Trust Security Interception**:
  * Every tool call sends telemetry and argument payloads to AgentShield (`POST /api/v1/decide`).
  * Attaches Groq's reasoning (`_reasoning`) so security teams see the AI's exact thought process inside the AgentShield dashboard.
  * Automatically handles `ShieldBlocked` (sending polite security notices) and `ShieldEscalated` (notifying customer of Human-in-the-Loop review).
* **1,000+ Customer Spectrum CRM**:
  * Built-in in-memory SQLite CRM pre-seeded with **1,001 customers (`1000` to `2000` inclusive)**.
  * Each customer record contains verified realistic details: Full Name, Email, 10-digit Phone, Street Address, **12-digit Indian Aadhaar** (`XXXX XXXX XXXX`), **10-digit PAN** (`ABCDE1234F`), and Order History.
  * Dynamic fallback generator guarantees no customer ID in range 1000–2000 is ever returned as "not found".
* **Dual Operation Modes**:
  * **Daemon Mode**: Continuously listens to unread emails via IMAP, writes automated replies, and sends them via SMTP.
  * **Interactive / Demo Runner**: Runs built-in test suites covering normal inquiries, PII exfiltration attempts, prompt injections, and destructive commands.

---

## 🧰 Supported Agent Tools

| Tool | Action | Protected Classification | Policy Behavior |
| :--- | :--- | :--- | :--- |
| `get_customer(customer_id)` | Fetches customer profile (name, address, Aadhaar, PAN) | `internal` | Sensitive data monitored; PII masked |
| `get_customer_orders(customer_id)` | Looks up order tracking and delivery history | `internal` | `ALLOW` |
| `search_customer(email)` | Finds customer by email address | `internal` | `ALLOW` |
| `issue_refund(order_id, amount)` | Issues refund for order | `internal` | Escalates to `HITL` if over threshold |
| `send_email(to, subject, body)` | Forwards data to external recipient | `internal` | Blocked if exfiltrating PII |
| `delete_customer(customer_id)` | Attempts to delete customer account | `restricted` | Hard `BLOCK` by security policy |

---

## ⚙️ Configuration & Setup

### 1. Environment Variables

Create a `.env` file in the project root:

```bash
# AgentShield Security Gateway
AGENTSHIELD_URL=http://localhost:8000
AGENTSHIELD_API_KEY=ash_your_agent_api_key_here

# Groq LLM Key
GROQ_API_KEY=gsk_your_groq_api_key_here

# Optional: Real Gmail Inbox Integration (Leave blank to use Demo Runner)
GMAIL_ADDRESS=your.support.bot@gmail.com
GMAIL_APP_PASSWORD=your_16_char_app_password
```

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/Skanda001/email-support-agent.git
cd email-support-agent

# Set up virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
# source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Running the Agent

### Option A: Local Test Runner / Scenario Simulator
Executes diverse test emails against the agent to verify tool decisions, security enforcement, and replies:

```bash
python run.py
```

### Option B: Direct Python Integration
You can import and invoke the agent programmatically:

```python
from agent.email_agent import EmailSupportAgent
from agent.email_client import InboundEmail

agent = EmailSupportAgent()

email = InboundEmail(
    msg_id="MSG-101",
    from_addr="alice@example.com",
    subject="Order Update",
    body="Can you please check the delivery status for customer 1001?"
)

response = agent.process(email)
print("Verdict:", response["verdict"])
print("Reply:\n", response["reply"])
```

---

## 🤖 GitHub Actions Automation

The repository includes a recurring workflow (`.github/workflows/agent.yml`) that runs every 10 minutes to process incoming emails automatically on a schedule.

To configure:
1. Go to **Settings → Secrets and variables → Actions**
2. Add `GROQ_API_KEY`, `AGENTSHIELD_URL`, `AGENTSHIELD_API_KEY`, `GMAIL_ADDRESS`, and `GMAIL_APP_PASSWORD`.

---

## 📄 License

MIT License. Built as an open reference implementation of Zero-Trust AI agent architectures.
