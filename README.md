# Email Support Agent

An autonomous AI customer support agent that monitors a Gmail inbox, processes support emails using Groq LLM, and enforces security policies via [AgentShield](https://github.com/Skanda001/agentshield).

## Architecture

```
Gmail Inbox (IMAP)
      │  unread email arrives
      ▼
Groq LLM reads email
      │  decides which tool to call
      ▼
@protect decorator
      │  HTTP POST → AgentShield gateway
      ▼
AgentShield processes:
  • PII detection
  • Prompt injection detection
  • Policy engine
  • Kill switch
      │
   ┌──┴──────────┐
   ▼             ▼
ALLOW          BLOCK / HITL
   │             │
tool runs     reply explains
Groq writes   why it was blocked
reply            │
   └──────┬──────┘
          ▼
   Gmail SMTP → reply sent
```

> **AgentShield is a completely separate service.** This agent is just a client — it connects via HTTP using an API key.

## Setup

### 1. Create a new GitHub repository
Push this project to its own repo (e.g. `email-support-agent`).

### 2. Add GitHub Secrets
Go to **Settings → Secrets and variables → Actions → New repository secret**:

| Secret | Value |
|--------|-------|
| `AGENTSHIELD_URL` | `https://agentshield-qhxo.onrender.com` |
| `AGENTSHIELD_API_KEY` | *(leave blank — auto-provisions on first run)* |
| `GMAIL_ADDRESS` | `agentshield.demo@gmail.com` |
| `GMAIL_APP_PASSWORD` | your 16-char Gmail app password |
| `GROQ_API_KEY` | your Groq API key |

### 3. Enable IMAP on Gmail
Sign into the Gmail account → **Settings → See all settings → Forwarding and POP/IMAP → Enable IMAP → Save**

### 4. Trigger first run
**Actions → AgentShield Email Support Agent → Run workflow**

Copy the printed `AGENTSHIELD_API_KEY` from the logs → save it as a secret.

### 5. Done ✅
The agent runs every 10 minutes automatically. Send an email to the Gmail address and get an AI-powered reply.

## What it can do

| Tool | Triggers when email asks about |
|------|-------------------------------|
| `get_customer` | customer profile / account details |
| `get_customer_orders` | order status / shipping / tracking |
| `search_customer` | an email address is mentioned |
| `issue_refund` | refund or return |
| `send_email` | forwarding something to someone |
| `delete_customer` | delete account → **BLOCKED by AgentShield** |

## Security responses

| AgentShield verdict | What the customer receives |
|---------------------|---------------------------|
| ✅ ALLOW | Helpful reply with the requested information |
| ⛔ BLOCK | Email explaining the request was blocked and why |
| ⚠️ HITL | Email saying a supervisor will review within 30 min |

## Fallback mode
When the inbox is empty, the agent runs a random security scenario (PII exfiltration attempt, prompt injection, normal query) to keep the AgentShield dashboard showing live activity.
