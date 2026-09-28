"""Customer support tools protected by AgentShield @protect decorator."""
from __future__ import annotations
from typing import Any
from agent.data import crm
from agent.shield import protect


@protect(tool="search_customer", resource_type="customer", data_classification="internal")
def search_customer(email: str) -> dict[str, Any]:
    res = crm.search_by_email(email)
    return res or {"found": False, "email": email}


@protect(tool="get_customer", resource_type="customer", data_classification="internal")
def get_customer(customer_id: int) -> dict[str, Any]:
    res = crm.get_customer(customer_id)
    return res or {"found": False, "customer_id": customer_id}


@protect(tool="get_customer_orders", resource_type="order", data_classification="internal")
def get_customer_orders(customer_id: int) -> list[dict[str, Any]]:
    return crm.get_orders(customer_id)


@protect(tool="issue_refund", resource_type="payment", data_classification="internal")
def issue_refund(order_id: int, amount: float) -> dict[str, Any]:
    return crm.refund_order(order_id, amount)


@protect(tool="send_email", resource_type="email", data_classification="internal")
def send_email(to: str, subject: str, body: str) -> dict[str, Any]:
    return {"sent": True, "to": to, "subject": subject}


@protect(tool="delete_customer", resource_type="customer", data_classification="restricted")
def delete_customer(customer_id: int) -> dict[str, Any]:
    return crm.delete_customer(customer_id)
