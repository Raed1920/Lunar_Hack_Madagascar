import json
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kafka import KafkaProducer

BROKER = "localhost:9092"
CURRENCY = "TND"
TOPICS = {
    "customers": "customers",
    "products": "products",
    "orders": "orders",
    "order_items": "order-items",
    "website_behavior": "website-behavior",
    "conversations": "conversations",
    "marketing_campaigns": "marketing-campaigns",
    "transactions": "transactions",
}

producer = KafkaProducer(
    bootstrap_servers=BROKER,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: k.encode("utf-8"),
)

FIRST_NAMES = [
    "Raed",
    "Sana",
    "Omar",
    "Nour",
    "Aymen",
    "Lina",
    "Yassine",
    "Malek",
    "Hedi",
    "Meriem",
    "Aziz",
    "Amira",
]
LOCATIONS = ["Tunis", "Sfax", "Sousse", "Ariana", "Bizerte", "Gabes", "Nabeul", "Monastir", "Kairouan"]
SEGMENTS = ["VIP", "new", "regular", "inactive_users", "at_risk", "churned"]
CAMPAIGN_TYPES = ["email", "sms", "push", "retargeting_ads"]
ORDER_STATUSES = ["completed", "pending", "cancelled", "refunded"]
WEB_EVENTS = ["view_product", "add_to_cart", "checkout_started", "abandoned_cart"]
MAIL_WEBHOOK_URLS = [
    "http://localhost:5678/webhook-test/send-mails",
    "http://localhost:5678/webhook/send-mails",
]
TARGET_EMAILS = ["chaabane.boussadia@etudiant-fst.utm.tn", "raedfac1920@gmail.com"]
EMAIL_COOLDOWN_SECONDS = 90
MAIL_RETRY_SECONDS = 8
MAIL_MAX_RETRIES = 40

PRODUCTS = {
    "P001": {
        "id": "P001",
        "name": "Espadrilles Carthage",
        "category": "Chaussures",
        "price": 189.0,
        "stock": 60,
        "created_at": "2025-03-01",
        "currency": CURRENCY,
    },
    "P002": {
        "id": "P002",
        "name": "Sneakers Medina",
        "category": "Chaussures",
        "price": 149.0,
        "stock": 70,
        "created_at": "2025-03-05",
        "currency": CURRENCY,
    },
    "P003": {
        "id": "P003",
        "name": "Hoodie Djerba",
        "category": "Vetements",
        "price": 109.0,
        "stock": 90,
        "created_at": "2025-04-01",
        "currency": CURRENCY,
    },
    "P004": {
        "id": "P004",
        "name": "Jean Sidi Bou Said",
        "category": "Vetements",
        "price": 129.0,
        "stock": 55,
        "created_at": "2025-04-18",
        "currency": CURRENCY,
    },
    "P005": {
        "id": "P005",
        "name": "Casquette Tozeur",
        "category": "Accessoires",
        "price": 49.0,
        "stock": 120,
        "created_at": "2025-05-02",
        "currency": CURRENCY,
    },
    "P006": {
        "id": "P006",
        "name": "Sac Hammamet",
        "category": "Accessoires",
        "price": 89.0,
        "stock": 80,
        "created_at": "2025-05-15",
        "currency": CURRENCY,
    },
}

CUSTOMERS = {}
NEXT_ORDER_ID = 1
NEXT_CAMPAIGN_ID = 1
LOW_CONVERSION_CUSTOMERS: List[str] = []
NEW_CUSTOMERS: List[str] = []
VIP_AT_RISK_CUSTOMERS: List[str] = []
LAST_MAIL_SENT_AT: Dict[str, float] = {}
PENDING_MAILS: Dict[str, Dict[str, object]] = {}


def iso_now() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def random_date_since(year: int = 2025) -> str:
    start = datetime(year, 1, 1)
    end = datetime.utcnow()
    delta_days = max(1, (end - start).days)
    return (start + timedelta(days=random.randint(0, delta_days))).strftime("%Y-%m-%d")


def emit(topic_key: str, payload: dict, key: str) -> None:
    producer.send(TOPICS[topic_key], key=key, value=payload)


def build_customer(customer_id: str) -> dict:
    name = random.choice(FIRST_NAMES)
    created_at = random_date_since(2025)
    return {
        "id": customer_id,
        "name": name,
        "email": random.choice(TARGET_EMAILS),
        "segment": random.choices(SEGMENTS, weights=[0.12, 0.18, 0.45, 0.15, 0.06, 0.04])[0],
        "location": random.choice(LOCATIONS),
        "created_at": created_at,
        "last_active": random_date_since(2025),
    }


def classify_mail_reason(customer: dict) -> Optional[str]:
    segment = str(customer.get("segment", "")).strip().lower()
    if segment == "vip":
        return "high_value"
    if segment in {"at_risk", "churned", "inactive_users", "vip_at_risk"}:
        return "churn_risk"
    return None


def should_send_mail(customer_id: str, reason: str) -> bool:
    key = f"{customer_id}:{reason}"
    now_ts = time.time()
    last_ts = LAST_MAIL_SENT_AT.get(key, 0.0)
    if now_ts - last_ts < EMAIL_COOLDOWN_SECONDS:
        return False
    return True


def build_mail_payload(customer: dict, reason: str, trigger_source: str) -> dict:
    customer_id = str(customer.get("id", "unknown"))
    to_addr = str(customer.get("email", "")).strip() or random.choice(TARGET_EMAILS)
    customer_name = str(customer.get("name", customer_id))
    segment = str(customer.get("segment", ""))

    if reason == "high_value":
        subject = f"Merci {customer_name} - Offre VIP exclusive"
        body_html = (
            f"<p>Bonjour {customer_name},</p>"
            "<p>Merci pour votre fidelite. Vous faites partie de nos clients a haute valeur.</p>"
            "<p>Profitez d'une offre VIP reservee a votre segment.</p>"
        )
        campaign_type = "vip_retention"
    else:
        subject = f"On vous attend {customer_name} - Offre de retour"
        body_html = (
            f"<p>Bonjour {customer_name},</p>"
            "<p>Nous avons remarque une baisse d'activite sur votre compte.</p>"
            "<p>Revenez avec une offre speciale de reactivation valable aujourd'hui.</p>"
        )
        campaign_type = "churn_reactivation"

    return {
        "to": to_addr,
        "customer_name": customer_name,
        "subject": subject,
        "body_html": body_html,
        "campaign_type": campaign_type,
        "personalization_tokens": {
            "customer_id": customer_id,
            "segment": segment,
            "reason": reason,
            "trigger_source": trigger_source,
        },
    }


def post_mail_payload(payload: dict) -> Tuple[bool, str]:
    variants = [payload, {"emails": [payload]}]
    last_error = "unknown error"
    for url in MAIL_WEBHOOK_URLS:
        for body_obj in variants:
            body = json.dumps(body_obj).encode("utf-8")
            req = Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urlopen(req, timeout=5) as resp:
                    status = int(getattr(resp, "status", 200))
                    if 200 <= status < 300:
                        return True, f"{url} status={status}"
                    last_error = f"{url} status={status}"
            except HTTPError as exc:
                last_error = f"{url} HTTP {exc.code}"
            except URLError as exc:
                last_error = f"{url} unreachable: {exc.reason}"
    return False, last_error


def queue_mail_retry(customer_id: str, reason: str, payload: dict, trigger_source: str, error: str) -> None:
    key = f"{customer_id}:{reason}"
    now_ts = time.time()
    pending = PENDING_MAILS.get(key)
    if pending:
        pending["last_error"] = error
        return
    PENDING_MAILS[key] = {
        "customer_id": customer_id,
        "reason": reason,
        "payload": payload,
        "trigger_source": trigger_source,
        "attempts": 1,
        "next_try_at": now_ts + MAIL_RETRY_SECONDS,
        "last_error": error,
    }
    print(f"[MAIL QUEUED] {customer_id} {reason} retry_in={MAIL_RETRY_SECONDS}s ({error})")


def retry_pending_mails() -> None:
    if not PENDING_MAILS:
        return
    now_ts = time.time()
    for key, pending in list(PENDING_MAILS.items()):
        next_try_at = float(pending.get("next_try_at", 0.0))
        if now_ts < next_try_at:
            continue
        payload = dict(pending.get("payload", {}))
        ok, info = post_mail_payload(payload)
        customer_id = str(pending.get("customer_id", "unknown"))
        reason = str(pending.get("reason", "unknown"))
        if ok:
            LAST_MAIL_SENT_AT[key] = now_ts
            del PENDING_MAILS[key]
            print(f"[MAIL SENT] {customer_id} {reason} -> {payload.get('to', '')} via retry ({info})")
            continue

        attempts = int(pending.get("attempts", 1)) + 1
        if attempts > MAIL_MAX_RETRIES:
            del PENDING_MAILS[key]
            print(f"[MAIL DROP] {customer_id} {reason} retries_exhausted ({info})")
            continue
        pending["attempts"] = attempts
        pending["last_error"] = info
        pending["next_try_at"] = now_ts + MAIL_RETRY_SECONDS


def send_mail_for_customer(customer: dict, reason: str, trigger_source: str) -> None:
    customer_id = str(customer.get("id", ""))
    if not customer_id or not should_send_mail(customer_id, reason):
        return
    payload = build_mail_payload(customer, reason, trigger_source)
    ok, info = post_mail_payload(payload)
    if ok:
        LAST_MAIL_SENT_AT[f"{customer_id}:{reason}"] = time.time()
        print(f"[MAIL SENT] {customer_id} {reason} -> {payload['to']} ({info})")
        return
    queue_mail_retry(customer_id, reason, payload, trigger_source, info)


def seed_reference_data() -> None:
    for i in range(1, 101):
        customer_id = f"C{i:03d}"
        customer = build_customer(customer_id)
        if i <= 4:
            customer["segment"] = "VIP"
            customer["created_at"] = (datetime.utcnow() - timedelta(days=random.randint(20, 120))).strftime("%Y-%m-%d")
            VIP_AT_RISK_CUSTOMERS.append(customer_id)
        if i <= 12:
            customer["segment"] = "new"
            customer["created_at"] = (datetime.utcnow() - timedelta(days=random.randint(0, 10))).strftime("%Y-%m-%d")
            NEW_CUSTOMERS.append(customer_id)
        if 13 <= i <= 24:
            customer["segment"] = random.choice(["at_risk", "churned"])
        if i <= 8:
            LOW_CONVERSION_CUSTOMERS.append(customer_id)
        CUSTOMERS[customer_id] = customer
        emit("customers", customer, customer["id"])

    for product in PRODUCTS.values():
        emit("products", product, product["id"])

    for _ in range(3):
        emit("marketing_campaigns", generate_campaign(), f"M{NEXT_CAMPAIGN_ID - 1:03d}")

    producer.flush()


def pick_customer() -> dict:
    customer = CUSTOMERS[random.choice(list(CUSTOMERS.keys()))]
    customer["last_active"] = datetime.utcnow().strftime("%Y-%m-%d")
    return customer


def generate_campaign() -> dict:
    global NEXT_CAMPAIGN_ID
    campaign = {
        "id": f"M{NEXT_CAMPAIGN_ID:03d}",
        "type": random.choice(CAMPAIGN_TYPES),
        "target_segment": random.choice(SEGMENTS),
        "created_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "conversion_rate": round(random.uniform(0.02, 0.25), 2),
    }
    NEXT_CAMPAIGN_ID += 1
    return campaign


def generate_behavior() -> dict:
    customer = pick_customer()
    product = random.choice(list(PRODUCTS.values()))
    return {
        "customer_id": customer["id"],
        "event": random.choices(WEB_EVENTS, weights=[0.52, 0.23, 0.15, 0.10])[0],
        "product_id": product["id"],
        "timestamp": iso_now(),
    }


def generate_low_conversion_behavior() -> dict:
    customer_id = random.choice(LOW_CONVERSION_CUSTOMERS) if LOW_CONVERSION_CUSTOMERS else pick_customer()["id"]
    product = random.choice(list(PRODUCTS.values()))
    return {
        "customer_id": customer_id,
        "event": random.choices(
            ["view_product", "add_to_cart", "abandoned_cart"],
            weights=[0.55, 0.20, 0.25],
        )[0],
        "product_id": product["id"],
        "timestamp": iso_now(),
    }


def generate_mail_trigger_events() -> List[dict]:
    customer_id = random.choice(VIP_AT_RISK_CUSTOMERS) if VIP_AT_RISK_CUSTOMERS else pick_customer()["id"]
    product_ids = [p["id"] for p in random.sample(list(PRODUCTS.values()), k=3)]
    events: List[dict] = []

    # Guarantees backend email-target rules:
    # - low_conversion: views >= 6 and no completed order needed for this customer
    # - vip_at_risk: segment VIP + abandoned_cart >= 2 + completed == 0
    for _ in range(6):
        events.append(
            {
                "customer_id": customer_id,
                "event": "view_product",
                "product_id": random.choice(product_ids),
                "timestamp": iso_now(),
            }
        )
    for _ in range(2):
        events.append(
            {
                "customer_id": customer_id,
                "event": "abandoned_cart",
                "product_id": random.choice(product_ids),
                "timestamp": iso_now(),
            }
        )
    events.append(
        {
            "customer_id": customer_id,
            "event": "add_to_cart",
            "product_id": random.choice(product_ids),
            "timestamp": iso_now(),
        }
    )
    return events


def create_new_customer_event() -> dict:
    customer_id = f"C{len(CUSTOMERS)+1:03d}"
    customer = build_customer(customer_id)
    customer["segment"] = "new"
    customer["created_at"] = datetime.utcnow().strftime("%Y-%m-%d")
    customer["last_active"] = datetime.utcnow().strftime("%Y-%m-%d")
    CUSTOMERS[customer_id] = customer
    NEW_CUSTOMERS.append(customer_id)
    return customer


def generate_new_customer_order() -> Tuple[dict, List[dict]]:
    global NEXT_ORDER_ID
    if NEW_CUSTOMERS:
        cid = random.choice(NEW_CUSTOMERS)
        customer = CUSTOMERS[cid]
    else:
        customer = pick_customer()
    status = random.choices(["completed", "pending", "cancelled"], weights=[0.45, 0.40, 0.15])[0]
    products = random.sample(list(PRODUCTS.values()), k=random.randint(1, 2))
    items: List[dict] = []
    total = 0.0
    for product in products:
        quantity = random.randint(1, 2)
        items.append(
            {
                "order_id": f"O{NEXT_ORDER_ID:03d}",
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": quantity,
                "price": product["price"],
                "currency": CURRENCY,
            }
        )
        total += product["price"] * quantity
    order = {
        "id": f"O{NEXT_ORDER_ID:03d}",
        "customer_id": customer["id"],
        "total": round(total, 2),
        "status": status,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "currency": CURRENCY,
    }
    NEXT_ORDER_ID += 1
    return order, items


def generate_conversation() -> dict:
    customer = pick_customer()
    messages = [
        "Salem, je cherche des baskets confortables.",
        "Vous avez une promo ce week-end ?",
        "Nheb nbadel la taille de ma commande.",
        "Je n'arrive pas a payer par carte.",
        "Quand est-ce que la livraison vers Sfax arrive ?",
        "Mon panier a disparu, pouvez-vous m'aider ?",
    ]
    return {
        "customer_id": customer["id"],
        "message": random.choice(messages),
        "timestamp": datetime.utcnow().strftime("%Y-%m-%d"),
    }


def generate_order() -> Tuple[dict, List[dict]]:
    global NEXT_ORDER_ID
    customer = pick_customer()
    status = random.choices(ORDER_STATUSES, weights=[0.70, 0.16, 0.08, 0.06])[0]
    products = random.sample(list(PRODUCTS.values()), k=random.randint(1, 4))
    items: List[dict] = []
    total = 0.0

    for product in products:
        quantity = random.randint(1, 3)
        items.append(
            {
                "order_id": f"O{NEXT_ORDER_ID:03d}",
                "product_id": product["id"],
                "product_name": product["name"],
                "quantity": quantity,
                "price": product["price"],
                "currency": CURRENCY,
            }
        )
        total += product["price"] * quantity
        if status in {"completed", "pending"}:
            product["stock"] = max(0, product["stock"] - quantity)

    order = {
        "id": f"O{NEXT_ORDER_ID:03d}",
        "customer_id": customer["id"],
        "total": round(total, 2),
        "status": status,
        "created_at": datetime.utcnow().strftime("%Y-%m-%d"),
        "currency": CURRENCY,
    }
    NEXT_ORDER_ID += 1
    return order, items


def mutate_product() -> dict:
    product = random.choice(list(PRODUCTS.values()))
    stock_shift = random.randint(-8, 24)
    price_shift = random.uniform(-6, 8)
    product["stock"] = max(0, product["stock"] + stock_shift)
    product["price"] = max(20, round(product["price"] + price_shift, 2))
    return product


print(f"Simulator running on {BROKER}")
print("Topics:", ", ".join(TOPICS.values()))
print(f"Currency: {CURRENCY}")
print("Ctrl+C to stop\n")

seed_reference_data()

while True:
    retry_pending_mails()
    scenario = random.choices(
        [
            "website_behavior",
            "orders",
            "conversations",
            "marketing_campaigns",
            "customers",
            "products",
            "low_conversion_pattern",
            "new_customer_case",
            "mail_trigger_case",
        ],
        weights=[0.27, 0.22, 0.12, 0.08, 0.06, 0.05, 0.10, 0.05, 0.05],
    )[0]

    if scenario == "website_behavior":
        payload = generate_behavior()
        emit("website_behavior", payload, payload["customer_id"])
        customer = CUSTOMERS.get(payload["customer_id"])
        if customer:
            reason = classify_mail_reason(customer)
            if reason:
                send_mail_for_customer(customer, reason, "website_behavior")
        print(f"[WEB] {payload['customer_id']} {payload['event']} {payload['product_id']}")
    elif scenario == "orders":
        order, items = generate_order()
        emit("orders", order, order["id"])
        emit("transactions", order, order["id"])
        for item in items:
            emit("order_items", item, item["order_id"])
        customer = CUSTOMERS.get(order["customer_id"])
        if customer:
            reason = classify_mail_reason(customer)
            if reason:
                send_mail_for_customer(customer, reason, "order_event")
        print(f"[ORDER] {order['id']} {order['status']} total={order['total']} {CURRENCY}")
    elif scenario == "conversations":
        payload = generate_conversation()
        emit("conversations", payload, payload["customer_id"])
        print(f"[CHAT] {payload['customer_id']}: {payload['message']}")
    elif scenario == "marketing_campaigns":
        payload = generate_campaign()
        emit("marketing_campaigns", payload, payload["id"])
        print(f"[MKT] {payload['id']} {payload['type']} segment={payload['target_segment']}")
    elif scenario == "customers":
        payload = pick_customer()
        emit("customers", payload, payload["id"])
        reason = classify_mail_reason(payload)
        if reason:
            send_mail_for_customer(payload, reason, "customer_refresh")
        print(f"[CUSTOMER] {payload['id']} {payload['location']} segment={payload['segment']}")
    elif scenario == "low_conversion_pattern":
        for _ in range(random.randint(2, 4)):
            payload = generate_low_conversion_behavior()
            emit("website_behavior", payload, payload["customer_id"])
            customer = CUSTOMERS.get(payload["customer_id"])
            if customer:
                reason = classify_mail_reason(customer)
                if reason:
                    send_mail_for_customer(customer, reason, "low_conversion_pattern")
        print("[ANOMALY] low-conversion browsing burst emitted")
    elif scenario == "new_customer_case":
        if random.random() < 0.45:
            payload = create_new_customer_event()
            emit("customers", payload, payload["id"])
            print(f"[NEW CUSTOMER] {payload['id']} {payload['email']}")
        else:
            order, items = generate_new_customer_order()
            emit("orders", order, order["id"])
            emit("transactions", order, order["id"])
            for item in items:
                emit("order_items", item, item["order_id"])
            print(f"[NEW CUSTOMER ORDER] {order['id']} {order['status']} total={order['total']} {CURRENCY}")
    elif scenario == "mail_trigger_case":
        events = generate_mail_trigger_events()
        customer = CUSTOMERS.get(events[0]["customer_id"]) if events else None
        for payload in events:
            emit("website_behavior", payload, payload["customer_id"])
            if customer:
                reason = classify_mail_reason(customer)
                if reason:
                    send_mail_for_customer(customer, reason, "mail_trigger_case")
        print("[MAIL TRIGGER] deterministic VIP low-conversion + abandoned-cart burst emitted")
    else:
        payload = mutate_product()
        emit("products", payload, payload["id"])
        print(f"[PRODUCT] {payload['name']} stock={payload['stock']} price={payload['price']} {CURRENCY}")

    producer.flush()
    time.sleep(random.uniform(0.4, 2.0))
