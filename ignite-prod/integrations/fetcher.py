"""
External data fetcher.
Mock mode: returns sample data. Swap for real API calls by implementing
_fetch_ecom_orders_real() and _fetch_crm_distributors_real().
"""

import httpx
from datetime import date, datetime
from config import get_settings

settings = get_settings()


# ── Ecommerce orders ──────────────────────────────────────────────────────

async def fetch_ecom_orders(since: date) -> list[dict]:
    """Fetch verified orders from ecommerce platform since a given date."""
    if settings.ECOMMERCE_API.startswith("https://mock"):
        return _mock_ecom_orders(since)
    return await _fetch_ecom_orders_real(since)


async def _fetch_ecom_orders_real(since: date) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{settings.ECOMMERCE_API}/orders",
            headers={"Authorization": f"Bearer {settings.ECOMMERCE_API_KEY}"},
            params={"created_after": since.isoformat(), "status": "completed"},
        )
        response.raise_for_status()
        raw = response.json()

    # Normalize to our schema — adjust field names to match your actual API
    orders = []
    for item in raw.get("orders", []):
        orders.append({
            "ecom_order_id": str(item["id"]),
            "distributor_ref": str(item.get("customer_id") or item.get("distributor_id")),
            "order_date": item["created_at"][:10],
            "amount_inr": int(item["total_amount_inr"]),
            "items": [
                {
                    "sku": li["sku"],
                    "quantity": li["quantity"],
                    "unit_price_inr": int(li["unit_price_inr"]),
                }
                for li in item.get("line_items", [])
            ],
        })
    return orders


def _mock_ecom_orders(since: date) -> list[dict]:
    today = date.today().isoformat()
    return [
        {
            "ecom_order_id": "ECO-10001",
            "distributor_ref": "BA-0001",
            "order_date": today,
            "amount_inr": 51000,
            "items": [{"sku": "SAN-ACT", "quantity": 1, "unit_price_inr": 51000}],
        },
        {
            "ecom_order_id": "ECO-10002",
            "distributor_ref": "BA-0002",
            "order_date": today,
            "amount_inr": 102000,
            "items": [{"sku": "SAN-SIM", "quantity": 2, "unit_price_inr": 51000}],
        },
    ]


# ── CRM distributors ──────────────────────────────────────────────────────

async def fetch_new_distributors(since: date) -> list[dict]:
    """Fetch new distributor sign-ups from CRM since a given date."""
    if settings.CRM_API.startswith("https://mock"):
        return _mock_crm_distributors()
    return await _fetch_crm_distributors_real(since)


async def _fetch_crm_distributors_real(since: date) -> list[dict]:
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{settings.CRM_API}/distributors",
            headers={"Authorization": f"Bearer {settings.CRM_API_KEY}"},
            params={"registered_after": since.isoformat(), "status": "active"},
        )
        response.raise_for_status()
        raw = response.json()

    distributors = []
    for d in raw.get("distributors", []):
        distributors.append({
            "crm_id": str(d["id"]),
            "distributor_id": d.get("ba_code") or d.get("distributor_id"),
            "full_name": d["name"],
            "email": d["email"],
            "phone": d.get("mobile") or d.get("phone"),
            "pan_number": d.get("pan"),
            "joined_date": d.get("joined_date") or d.get("created_at", "")[:10],
            "sponsor_ref": d.get("sponsor_id"),
        })
    return distributors


def _mock_crm_distributors() -> list[dict]:
    today = date.today().isoformat()
    return [
        {
            "crm_id": "CRM-5001",
            "distributor_id": "BA-1001",
            "full_name": "Ravi Shankar",
            "email": "ravi@example.in",
            "phone": "9876543210",
            "pan_number": "ABCDE1234F",
            "joined_date": today,
            "sponsor_ref": "BA-0001",
        },
        {
            "crm_id": "CRM-5002",
            "distributor_id": "BA-1002",
            "full_name": "Priya Mehta",
            "email": "priya@example.in",
            "phone": "8765432109",
            "pan_number": "FGHIJ5678K",
            "joined_date": today,
            "sponsor_ref": "BA-0001",
        },
    ]
