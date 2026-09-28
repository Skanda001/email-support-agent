"""Gmail IMAP reader + SMTP sender using only Python stdlib."""
from __future__ import annotations
import email, email.utils, imaplib, logging, smtplib, ssl
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

log = logging.getLogger("email_client")

IMAP_HOST = "imap.gmail.com"
IMAP_PORT = 993
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587

SKIP_SENDER_PATTERNS = (
    "no-reply", "noreply", "donotreply", "do-not-reply",
    "mailer-daemon", "postmaster", "notifications@",
    "newsletter", "unsubscribe", "auto-confirm",
    "github.com", "vercel.com", "render.com", "google.com",
)


@dataclass
class InboundEmail:
    uid: str
    from_addr: str
    reply_to: str
    subject: str
    body: str


class GmailClient:
    def __init__(self, address: str, app_password: str) -> None:
        self.address  = address
        self.password = app_password.replace(" ", "")

    def fetch_unread(self) -> list[InboundEmail]:
        """Fetch UNSEEN emails, skip automated senders, mark all as Seen."""
        results: list[InboundEmail] = []

        with imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT) as imap:
            imap.login(self.address, self.password)
            imap.select("INBOX")
            _, data = imap.search(None, "UNSEEN")
            uids = data[0].split()

            for uid in uids:
                _, msg_data = imap.fetch(uid, "(RFC822)")
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                from_addr = email.utils.parseaddr(msg.get("From", ""))[1]
                reply_to  = email.utils.parseaddr(msg.get("Reply-To", msg.get("From", "")))[1]
                subject   = msg.get("Subject", "(no subject)")
                from_lower = from_addr.lower()

                if from_lower == self.address.lower():
                    log.info("⏭ Skipping self-sent: %s", subject)
                    continue
                if any(p in from_lower for p in SKIP_SENDER_PATTERNS):
                    log.info("⏭ Skipping automated (%s): %s", from_addr, subject)
                    continue

                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            p = part.get_payload(decode=True)
                            if p: body = p.decode("utf-8", errors="replace")
                            break
                else:
                    p = msg.get_payload(decode=True)
                    if p: body = p.decode("utf-8", errors="replace")

                results.append(InboundEmail(
                    uid=uid.decode(), from_addr=from_addr,
                    reply_to=reply_to or from_addr,
                    subject=subject, body=body.strip(),
                ))

            for uid in uids:
                imap.store(uid, "+FLAGS", "\\Seen")

        log.info("📬 %d support email(s) to process", len(results))
        return results

    def send_reply(self, to: str, subject: str, body: str) -> None:
        """Send plain-text reply via Gmail SMTP (STARTTLS)."""
        msg = MIMEMultipart("alternative")
        msg["From"]    = f"AgentShield Support <{self.address}>"
        msg["To"]      = to
        msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.login(self.address, self.password)
            smtp.sendmail(self.address, to, msg.as_string())

        log.info("📧 Reply sent to %s", to)
