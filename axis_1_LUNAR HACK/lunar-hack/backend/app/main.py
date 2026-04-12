import asyncio
import json
import os
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

# Add multi-agent-test to path so we can import agents
_AGENTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "multi-agent-test")
if _AGENTS_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_AGENTS_DIR))


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_today_str() -> str:
    return utc_now().strftime("%Y-%m-%d")


def parse_date(date_value: str) -> str:
    if not date_value:
        return ""
    return date_value[:10]


def days_since(date_value: str) -> int:
    try:
        dt = datetime.strptime(parse_date(date_value), "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return max(0, (utc_now() - dt).days)
    except ValueError:
        return 9999


def cart_segment(total: float) -> str:
    if total < 120:
        return "petit_panier"
    if total < 260:
        return "panier_moyen"
    return "gros_panier"


def map_reduce(
    records: Iterable[Dict[str, Any]],
    map_fn: Callable[[Dict[str, Any]], Dict[str, Any]],
    reduce_fn: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    initial: Dict[str, Any],
) -> Dict[str, Any]:
    acc = dict(initial)
    for record in records:
        mapped = map_fn(record)
        acc = reduce_fn(acc, mapped)
    return acc


def reduce_by_key(
    records: Iterable[Dict[str, Any]],
    key_fn: Callable[[Dict[str, Any]], str],
    value_fn: Callable[[Dict[str, Any]], float],
) -> Dict[str, float]:
    def mapper(row: Dict[str, Any]) -> Dict[str, Any]:
        return {"k": key_fn(row), "v": value_fn(row)}

    def reducer(acc: Dict[str, Any], mapped: Dict[str, Any]) -> Dict[str, Any]:
        key = mapped["k"]
        acc[key] = float(acc.get(key, 0.0)) + float(mapped["v"])
        return acc

    return map_reduce(records, mapper, reducer, {})


class KPIState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.day = utc_today_str()
        self.currency = "TND"
        self.products: Dict[str, Dict[str, Any]] = {}
        self.customers: Dict[str, Dict[str, Any]] = {}
        self.orders: Dict[str, Dict[str, Any]] = {}
        self.order_items_by_order: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        self.web_events: List[Dict[str, Any]] = []
        self.conversations: List[Dict[str, Any]] = []
        self.campaigns: List[Dict[str, Any]] = []
        self.last_updated = utc_now().isoformat()
        self.last_events: List[Dict[str, Any]] = []

    def _roll_day_if_needed(self) -> None:
        today = utc_today_str()
        if today != self.day:
            self.day = today
            self.orders = {}
            self.order_items_by_order = defaultdict(list)
            self.web_events = []
            self.conversations = []
            self.campaigns = []
            self.last_events = []

    def _remember_event(self, topic: str, payload: Dict[str, Any]) -> None:
        self.last_events.insert(
            0,
            {
                "topic": topic,
                "id": payload.get("id") or payload.get("order_id") or "-",
                "timestamp": payload.get("timestamp") or payload.get("created_at") or self.day,
            },
        )
        self.last_events = self.last_events[:16]

    def ingest(self, topic: str, payload: Dict[str, Any]) -> None:
        with self.lock:
            self._roll_day_if_needed()
            if topic == "products":
                product_id = str(payload.get("id", ""))
                if product_id:
                    self.products[product_id] = payload
            elif topic == "customers":
                customer_id = str(payload.get("id", ""))
                if customer_id:
                    self.customers[customer_id] = payload
            elif topic == "orders":
                order_id = str(payload.get("id", ""))
                if order_id and parse_date(str(payload.get("created_at", ""))) == self.day:
                    enriched = dict(payload)
                    enriched["ingested_hour"] = utc_now().strftime("%H")
                    self.orders[order_id] = enriched
            elif topic == "order-items":
                order_id = str(payload.get("order_id", ""))
                if order_id:
                    item = dict(payload)
                    pid = str(item.get("product_id", ""))
                    if pid in self.products:
                        item["product_name"] = self.products[pid].get("name", pid)
                    self.order_items_by_order[order_id].append(item)
                    self.order_items_by_order[order_id] = self.order_items_by_order[order_id][-24:]
            elif topic == "website-behavior":
                self.web_events.append(payload)
                self.web_events = self.web_events[-3000:]
            elif topic == "conversations":
                self.conversations.append(payload)
                self.conversations = self.conversations[-2000:]
            elif topic == "marketing-campaigns":
                self.campaigns.append(payload)
                self.campaigns = self.campaigns[-1000:]

            self._remember_event(topic, payload)
            self.last_updated = utc_now().isoformat()

    def _order_matches_filters(
        self, order: Dict[str, Any], product_id: Optional[str], customer_id: Optional[str], cart_filter: Optional[str]
    ) -> bool:
        if customer_id and str(order.get("customer_id")) != customer_id:
            return False

        total = float(order.get("total", 0) or 0)
        if cart_filter and cart_filter != "tous_les_paniers" and cart_segment(total) != cart_filter:
            return False

        if product_id:
            order_id = str(order.get("id", ""))
            items = self.order_items_by_order.get(order_id, [])
            has_product = any(str(item.get("product_id")) == product_id for item in items)
            if not has_product:
                return False

        return True

    def _compute_from_filters(
        self, product_id: Optional[str], customer_id: Optional[str], cart_filter: Optional[str]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        filtered_orders = [
            order
            for order in self.orders.values()
            if self._order_matches_filters(order, product_id=product_id, customer_id=customer_id, cart_filter=cart_filter)
        ]

        filtered_order_ids = {str(order.get("id", "")) for order in filtered_orders}

        # MapReduce job #1: global order summary
        def map_order(order: Dict[str, Any]) -> Dict[str, Any]:
            total = float(order.get("total", 0) or 0)
            return {
                "revenue": total,
                "orders": 1,
                "completed": 1 if str(order.get("status", "")) == "completed" else 0,
            }

        def reduce_order(acc: Dict[str, Any], mapped: Dict[str, Any]) -> Dict[str, Any]:
            acc["revenue"] += mapped["revenue"]
            acc["orders"] += mapped["orders"]
            acc["completed"] += mapped["completed"]
            return acc

        order_summary = map_reduce(
            filtered_orders,
            map_order,
            reduce_order,
            {"revenue": 0.0, "orders": 0, "completed": 0},
        )

        # MapReduce jobs #2..#7: keyed aggregations
        order_status = reduce_by_key(
            filtered_orders,
            key_fn=lambda o: str(o.get("status", "unknown")),
            value_fn=lambda _o: 1,
        )
        revenue_by_hour = reduce_by_key(
            filtered_orders,
            key_fn=lambda o: str(o.get("ingested_hour", "00")),
            value_fn=lambda o: float(o.get("total", 0) or 0),
        )
        orders_by_hour = reduce_by_key(
            filtered_orders,
            key_fn=lambda o: str(o.get("ingested_hour", "00")),
            value_fn=lambda _o: 1,
        )
        customer_orders = reduce_by_key(
            filtered_orders,
            key_fn=lambda o: str(o.get("customer_id", "")),
            value_fn=lambda _o: 1,
        )
        customer_revenue = reduce_by_key(
            filtered_orders,
            key_fn=lambda o: str(o.get("customer_id", "")),
            value_fn=lambda o: float(o.get("total", 0) or 0),
        )
        cart_distribution = reduce_by_key(
            filtered_orders,
            key_fn=lambda o: cart_segment(float(o.get("total", 0) or 0)),
            value_fn=lambda _o: 1,
        )

        filtered_items = []
        for order_id in filtered_order_ids:
            filtered_items.extend(self.order_items_by_order.get(order_id, []))

        product_qty = reduce_by_key(
            filtered_items,
            key_fn=lambda i: str(i.get("product_id", "unknown")),
            value_fn=lambda i: float(int(i.get("quantity", 0) or 0)),
        )
        product_revenue = reduce_by_key(
            filtered_items,
            key_fn=lambda i: str(i.get("product_id", "unknown")),
            value_fn=lambda i: float(i.get("price", 0) or 0) * float(int(i.get("quantity", 0) or 0)),
        )

        filtered_web = []
        for event in self.web_events:
            if customer_id and str(event.get("customer_id", "")) != customer_id:
                continue
            if product_id and str(event.get("product_id", "")) != product_id:
                continue
            filtered_web.append(event)
        web_counts = reduce_by_key(
            filtered_web,
            key_fn=lambda e: str(e.get("event", "unknown")),
            value_fn=lambda _e: 1,
        )
        views = web_counts.get("view_product", 0)
        checkout_started = web_counts.get("checkout_started", 0)
        abandoned = web_counts.get("abandoned_cart", 0)
        completed_orders = float(order_summary["completed"])
        conversion_denominator = max(float(views), completed_orders)
        conversion = (completed_orders / conversion_denominator * 100.0) if conversion_denominator > 0 else 0.0
        abandonment_denominator = max(float(checkout_started), float(abandoned))
        abandonment = (float(abandoned) / abandonment_denominator * 100.0) if abandonment_denominator > 0 else 0.0
        conversion = min(100.0, max(0.0, conversion))
        abandonment = min(100.0, max(0.0, abandonment))
        average_basket = (order_summary["revenue"] / order_summary["orders"]) if order_summary["orders"] else 0.0

        conv_today = [
            c for c in self.conversations if (not customer_id or str(c.get("customer_id", "")) == customer_id)
        ]
        campaigns_today = [c for c in self.campaigns if parse_date(str(c.get("created_at", ""))) == self.day]

        top_products: List[Dict[str, Any]] = []
        for pid, qty in sorted(product_qty.items(), key=lambda kv: kv[1], reverse=True)[:6]:
            product = self.products.get(pid, {})
            top_products.append(
                {
                    "product_id": pid,
                    "product_name": product.get("name", pid),
                    "quantity": int(qty),
                    "revenue": round(product_revenue.get(pid, 0.0), 2),
                }
            )

        top_customers: List[Dict[str, Any]] = []
        for cid, count in sorted(customer_orders.items(), key=lambda kv: kv[1], reverse=True)[:6]:
            customer = self.customers.get(cid, {})
            top_customers.append(
                {
                    "customer_id": cid,
                    "customer_name": customer.get("name", cid),
                    "orders": int(count),
                    "revenue": round(customer_revenue.get(cid, 0.0), 2),
                }
            )

        hourly: List[Dict[str, Any]] = []
        for hour in [f"{h:02d}" for h in range(24)]:
            hourly.append(
                {
                    "hour": hour,
                    "revenue": round(float(revenue_by_hour.get(hour, 0.0)), 2),
                    "orders": int(float(orders_by_hour.get(hour, 0))),
                }
            )

        kpis = {
            "revenue_today": round(order_summary["revenue"], 2),
            "orders_today": int(order_summary["orders"]),
            "orders_completed": int(order_summary["completed"]),
            "conversion_rate": round(conversion, 2),
            "average_basket": round(average_basket, 2),
            "cart_abandonment_rate": round(abandonment, 2),
            "conversations_today": len(conv_today),
            "campaigns_today": len(campaigns_today),
        }
        cart_distribution_dict = dict(cart_distribution)
        cart_distribution_dict["tous_les_paniers"] = int(
            float(cart_distribution.get("petit_panier", 0))
            + float(cart_distribution.get("panier_moyen", 0))
            + float(cart_distribution.get("gros_panier", 0))
        )

        breakdowns = {
            "order_status": dict(order_status),
            "web_events": dict(web_counts),
            "top_products": top_products,
            "top_customers": top_customers,
            "cart_distribution": cart_distribution_dict,
            "hourly": hourly,
        }
        return kpis, breakdowns

    def _insights(self, kpis: Dict[str, Any], breakdowns: Dict[str, Any]) -> List[str]:
        insights: List[str] = []
        revenue = float(kpis["revenue_today"])
        conversion = float(kpis["conversion_rate"])
        abandonment = float(kpis["cart_abandonment_rate"])
        avg_basket = float(kpis["average_basket"])
        top_products = breakdowns["top_products"]

        if revenue > 12000:
            insights.append("Excellent dynamique commerciale aujourd'hui sur le marché tunisien.")
        elif kpis["orders_today"] > 8 and revenue < 1500:
            insights.append("Le volume est correct mais la valeur est faible: renforcer les bundles.")

        if conversion < 2.0 and breakdowns["web_events"].get("view_product", 0) > 20:
            insights.append("Conversion faible malgré trafic: simplifier la fiche produit et le checkout.")
        elif conversion > 8:
            insights.append("Conversion forte: opportunité d'augmenter le budget acquisition.")

        if abandonment > 30:
            insights.append("Abandon panier élevé: déclencher relances SMS/Email et vérifier les moyens de paiement.")

        if avg_basket < 90 and kpis["orders_today"] > 0:
            insights.append("Panier moyen bas: proposer cross-sell (accessoires, offres duo).")

        if top_products:
            insights.append(f"Produit moteur actuel: {top_products[0]['product_name']}.")

        if not insights:
            insights.append("Performance stable: continuer suivi des produits leaders et du tunnel de conversion.")
        return insights

    def snapshot(
        self, product_id: Optional[str] = None, customer_id: Optional[str] = None, cart_filter: Optional[str] = None
    ) -> Dict[str, Any]:
        with self.lock:
            self._roll_day_if_needed()
            kpis, breakdowns = self._compute_from_filters(
                product_id=product_id or None,
                customer_id=customer_id or None,
                cart_filter=cart_filter or None,
            )
            insights = self._insights(kpis, breakdowns)
            return {
                "day": self.day,
                "currency": self.currency,
                "last_updated": self.last_updated,
                "applied_filters": {
                    "product_id": product_id or "",
                    "customer_id": customer_id or "",
                    "cart_filter": cart_filter or "",
                },
                "catalog": {
                    "products": [
                        {"id": p["id"], "name": p.get("name", p["id"])}
                        for p in sorted(self.products.values(), key=lambda x: str(x.get("name", "")))
                    ],
                    "customers": [
                        {
                            "id": c["id"],
                            "name": c.get("name", c["id"]),
                            "email": c.get("email", ""),
                            "segment": c.get("segment", ""),
                            "created_at": c.get("created_at", ""),
                        }
                        for c in sorted(self.customers.values(), key=lambda x: str(x.get("name", "")))
                    ],
                    "cart_filters": [
                        {"id": "tous_les_paniers", "label": "Tous les paniers (somme totale)"},
                        {"id": "petit_panier", "label": "Petit panier (<120 TND)"},
                        {"id": "panier_moyen", "label": "Panier moyen (120-259 TND)"},
                        {"id": "gros_panier", "label": "Gros panier (>=260 TND)"},
                    ],
                },
                "kpis": kpis,
                "breakdowns": breakdowns,
                "insights": insights,
                "recent_activity": self.last_events,
            }

    def customer_targets(self) -> Dict[str, Any]:
        with self.lock:
            self._roll_day_if_needed()
            customer_orders_total: Counter = Counter()
            customer_completed_orders: Counter = Counter()
            customer_views: Counter = Counter()
            customer_add_to_cart: Counter = Counter()
            customer_abandoned: Counter = Counter()

            for order in self.orders.values():
                cid = str(order.get("customer_id", ""))
                if not cid:
                    continue
                customer_orders_total[cid] += 1
                if str(order.get("status", "")) == "completed":
                    customer_completed_orders[cid] += 1

            for event in self.web_events:
                cid = str(event.get("customer_id", ""))
                ev = str(event.get("event", ""))
                if not cid:
                    continue
                if ev == "view_product":
                    customer_views[cid] += 1
                elif ev == "add_to_cart":
                    customer_add_to_cart[cid] += 1
                elif ev == "abandoned_cart":
                    customer_abandoned[cid] += 1

            targets: List[Dict[str, Any]] = []
            for cid, customer in self.customers.items():
                email = str(customer.get("email", ""))
                if not email:
                    continue

                reasons: List[str] = []
                views = int(customer_views.get(cid, 0))
                completed = int(customer_completed_orders.get(cid, 0))
                abandoned = int(customer_abandoned.get(cid, 0))
                created_days = days_since(str(customer.get("created_at", "")))
                segment = str(customer.get("segment", ""))

                if views >= 6 and completed == 0:
                    reasons.append("low_conversion")
                if created_days <= 14 or segment == "new":
                    reasons.append("new_client")
                if segment == "VIP" and abandoned >= 2 and completed == 0:
                    reasons.append("vip_at_risk")

                if reasons:
                    targets.append(
                        {
                            "customer_id": cid,
                            "name": customer.get("name", cid),
                            "email": email,
                            "segment": segment,
                            "reasons": reasons,
                            "metrics": {
                                "views": views,
                                "add_to_cart": int(customer_add_to_cart.get(cid, 0)),
                                "abandoned_cart": abandoned,
                                "orders_total": int(customer_orders_total.get(cid, 0)),
                                "orders_completed": completed,
                            },
                        }
                    )

            return {
                "generated_at": utc_now().isoformat(),
                "count": len(targets),
                "targets": targets,
            }


class KafkaIngestor:
    def __init__(self, state: KPIState) -> None:
        self.state = state
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.broker = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.topics = [
            "products",
            "customers",
            "orders",
            "order-items",
            "website-behavior",
            "conversations",
            "marketing-campaigns",
        ]

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._consume, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _consume(self) -> None:
        while not self.stop_event.is_set():
            consumer = None
            try:
                consumer = KafkaConsumer(
                    *self.topics,
                    bootstrap_servers=self.broker,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    consumer_timeout_ms=1000,
                    group_id="realtime-kpi-dashboard",
                )
                while not self.stop_event.is_set():
                    for message in consumer:
                        payload = message.value if isinstance(message.value, dict) else {}
                        self.state.ingest(message.topic, payload)
                    time.sleep(0.05)
            except (KafkaError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"[KafkaIngestor] retrying after error: {exc}")
                time.sleep(2)
            finally:
                if consumer is not None:
                    consumer.close()


class SnapshotStreamProcessor:
    def __init__(self, state: KPIState) -> None:
        self.state = state
        self.broker = os.getenv("KAFKA_BROKER", "localhost:9092")
        self.topic = "kpi-snapshots"
        self.stop_event = threading.Event()
        self.publisher_thread: Optional[threading.Thread] = None
        self.consumer_thread: Optional[threading.Thread] = None
        self.history_lock = threading.Lock()
        self.history: List[Dict[str, Any]] = []

    def start(self) -> None:
        if not self.publisher_thread or not self.publisher_thread.is_alive():
            self.publisher_thread = threading.Thread(target=self._publish_loop, daemon=True)
            self.publisher_thread.start()
        if not self.consumer_thread or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self._consume_loop, daemon=True)
            self.consumer_thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.publisher_thread:
            self.publisher_thread.join(timeout=2)
        if self.consumer_thread:
            self.consumer_thread.join(timeout=2)

    def _build_stream_payload(self) -> Dict[str, Any]:
        snap = self.state.snapshot()
        return {
            "ts": utc_now().isoformat(),
            "day": snap["day"],
            "revenue_today": snap["kpis"]["revenue_today"],
            "orders_today": snap["kpis"]["orders_today"],
            "conversion_rate": snap["kpis"]["conversion_rate"],
            "average_basket": snap["kpis"]["average_basket"],
            "cart_abandonment_rate": snap["kpis"]["cart_abandonment_rate"],
        }

    def _publish_loop(self) -> None:
        producer = None
        while not self.stop_event.is_set():
            try:
                if producer is None:
                    producer = KafkaProducer(
                        bootstrap_servers=self.broker,
                        value_serializer=lambda v: json.dumps(v).encode("utf-8"),
                        key_serializer=lambda k: k.encode("utf-8"),
                    )
                payload = self._build_stream_payload()
                producer.send(self.topic, key="dashboard", value=payload)
                producer.flush()
                time.sleep(5)
            except (KafkaError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"[SnapshotPublisher] retrying after error: {exc}")
                if producer is not None:
                    producer.close()
                    producer = None
                time.sleep(2)
        if producer is not None:
            producer.close()

    def _consume_loop(self) -> None:
        while not self.stop_event.is_set():
            consumer = None
            try:
                consumer = KafkaConsumer(
                    self.topic,
                    bootstrap_servers=self.broker,
                    auto_offset_reset="latest",
                    enable_auto_commit=True,
                    value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                    consumer_timeout_ms=1000,
                    group_id="kpi-dashboard-stream",
                )
                while not self.stop_event.is_set():
                    for message in consumer:
                        payload = message.value if isinstance(message.value, dict) else {}
                        with self.history_lock:
                            self.history.append(payload)
                            self.history = self.history[-180:]
                    time.sleep(0.05)
            except (KafkaError, OSError, ValueError, json.JSONDecodeError) as exc:
                print(f"[SnapshotConsumer] retrying after error: {exc}")
                time.sleep(2)
            finally:
                if consumer is not None:
                    consumer.close()

    def get_history(self) -> List[Dict[str, Any]]:
        with self.history_lock:
            return list(self.history)


class AutonomousEmailAgent:
    def __init__(self, state: KPIState) -> None:
        self.state = state
        self.interval_seconds = float(os.getenv("EMAIL_AGENT_INTERVAL_SECONDS", "6"))
        self.cooldown_seconds = float(os.getenv("EMAIL_AGENT_COOLDOWN_SECONDS", "600"))
        self.stop_event = threading.Event()
        self.thread: Optional[threading.Thread] = None
        self.sent_lock = threading.Lock()
        self.sent_at_by_key: Dict[str, float] = {}
        urls_raw = os.getenv(
            "EMAIL_AGENT_WEBHOOK_URLS",
            "http://localhost:5678/webhook-test/send-email",
        )
        self.webhook_urls = [u.strip() for u in urls_raw.split(",") if u.strip()]

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.thread:
            self.thread.join(timeout=2)

    def _campaign_from_target(self, target: Dict[str, Any]) -> Optional[str]:
        reasons = {str(r).strip().lower() for r in target.get("reasons", [])}
        segment = str(target.get("segment", "")).strip().lower()
        if "vip_at_risk" in reasons:
            return "churn_reactivation"
        if segment == "vip":
            return "high_value_retention"
        if "low_conversion" in reasons:
            return "churn_reactivation"
        return None

    def _should_send(self, customer_id: str, campaign_type: str) -> bool:
        key = f"{customer_id}:{campaign_type}"
        now_ts = time.time()
        with self.sent_lock:
            last_ts = self.sent_at_by_key.get(key, 0.0)
            if now_ts - last_ts < self.cooldown_seconds:
                return False
        return True

    def _mark_sent(self, customer_id: str, campaign_type: str) -> None:
        key = f"{customer_id}:{campaign_type}"
        with self.sent_lock:
            self.sent_at_by_key[key] = time.time()

    def _build_email_payload(self, target: Dict[str, Any], campaign_type: str) -> Dict[str, Any]:
        customer_name = str(target.get("name", "Client"))
        customer_id = str(target.get("customer_id", ""))
        to_addr = str(target.get("email", "")).strip()
        reasons = [str(r) for r in target.get("reasons", [])]

        if campaign_type == "high_value_retention":
            subject = f"Merci {customer_name} - Offre VIP exclusive"
            body_html = (
                f"<p>Bonjour {customer_name},</p>"
                "<p>Merci pour votre fidelite. Vous etes parmi nos clients a haute valeur.</p>"
                "<p>Profitez d'une offre VIP reservee pour vous aujourd'hui.</p>"
            )
        else:
            subject = f"On vous attend {customer_name} - Offre de retour"
            body_html = (
                f"<p>Bonjour {customer_name},</p>"
                "<p>Nous avons remarque un risque d'attrition sur votre compte.</p>"
                "<p>Revenez des aujourd'hui avec une offre speciale de reactivation.</p>"
            )

        return {
            "to": to_addr,
            "customer_name": customer_name,
            "subject": subject,
            "body_html": body_html,
            "campaign_type": campaign_type,
            "personalization_tokens": {
                "customer_id": customer_id,
                "segment": str(target.get("segment", "")),
                "reasons": reasons,
                "source": "autonomous_email_agent",
            },
        }

    def _post_email(self, payload: Dict[str, Any]) -> Tuple[bool, str]:
        variants = [payload, {"emails": [payload]}]
        last_error = "webhook call failed"
        for url in self.webhook_urls:
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

    def _run_once(self) -> None:
        targets_payload = self.state.customer_targets()
        targets = targets_payload.get("targets", [])
        for target in targets:
            customer_id = str(target.get("customer_id", ""))
            if not customer_id:
                continue
            campaign_type = self._campaign_from_target(target)
            if not campaign_type:
                continue
            if not self._should_send(customer_id, campaign_type):
                continue
            payload = self._build_email_payload(target, campaign_type)
            if not payload.get("to"):
                continue
            ok, info = self._post_email(payload)
            if ok:
                self._mark_sent(customer_id, campaign_type)
                print(f"[EmailAgent] sent {campaign_type} to {payload['to']} ({info})")
            else:
                print(f"[EmailAgent] failed {campaign_type} for {customer_id}: {info}")

    def _run_loop(self) -> None:
        while not self.stop_event.is_set():
            try:
                self._run_once()
            except (TypeError, ValueError, KeyError) as exc:
                print(f"[EmailAgent] retrying after error: {exc}")
            time.sleep(self.interval_seconds)


state = KPIState()
ingestor = KafkaIngestor(state)
stream_processor = SnapshotStreamProcessor(state)
email_agent = AutonomousEmailAgent(state)
app = FastAPI(title="Real-time KPI API", version="1.3.0")

# Thread pool for running CrewAI agents (blocking LLM calls)
_agent_executor = ThreadPoolExecutor(max_workers=2)

# Cache last agent analysis result
_agent_cache: Dict[str, Any] = {}
_agent_cache_lock = threading.Lock()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5176"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def build_payload(product_id: str = "", customer_id: str = "", cart_filter: str = "") -> Dict[str, Any]:
    snap = state.snapshot(product_id=product_id, customer_id=customer_id, cart_filter=cart_filter)
    snap["stream"] = {"history": stream_processor.get_history()}
    return snap


@app.on_event("startup")
def on_startup() -> None:
    ingestor.start()
    stream_processor.start()
    email_agent.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    ingestor.stop()
    stream_processor.stop()
    email_agent.stop()


@app.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/kpis")
def get_kpis(
    product_id: str = Query(default=""),
    customer_id: str = Query(default=""),
    cart_filter: str = Query(default=""),
) -> Dict[str, Any]:
    return build_payload(product_id=product_id, customer_id=customer_id, cart_filter=cart_filter)


@app.get("/api/insights")
def get_insights(
    product_id: str = Query(default=""),
    customer_id: str = Query(default=""),
    cart_filter: str = Query(default=""),
) -> Dict[str, Any]:
    snapshot = build_payload(product_id=product_id, customer_id=customer_id, cart_filter=cart_filter)
    return {"day": snapshot["day"], "insights": snapshot["insights"]}


@app.get("/api/customer-targets")
def get_customer_targets() -> Dict[str, Any]:
    return state.customer_targets()


@app.post("/api/agent-analysis")
async def run_agent_analysis(
    product_id: str = Query(default=""),
    customer_id: str = Query(default=""),
    cart_filter: str = Query(default=""),
) -> Dict[str, Any]:
    """
    Trigger the 3-agent CrewAI pipeline on the current live KPI snapshot.
    Returns KPI analysis, customer emails (high-value + churn), and external research.
    """
    loop = asyncio.get_event_loop()

    def _run() -> Dict[str, Any]:
        try:
            from agents import run_kpi_analysis  # lazy import
        except ImportError as exc:
            return {"error": f"agents module not found: {exc}"}

        snapshot = build_payload(
            product_id=product_id,
            customer_id=customer_id,
            cart_filter=cart_filter,
        )
        result = run_kpi_analysis(snapshot)
        with _agent_cache_lock:
            _agent_cache.clear()
            _agent_cache.update(result)
        return result

    try:
        result = await loop.run_in_executor(_agent_executor, _run)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/agent-analysis/last")
def get_last_agent_analysis() -> Dict[str, Any]:
    """Return the most recently cached agent analysis (or empty if none yet)."""
    with _agent_cache_lock:
        if not _agent_cache:
            return {"status": "no_analysis_yet", "message": "Lance une analyse via POST /api/agent-analysis"}
        return dict(_agent_cache)


# ── Smart Recommendations (Agent 4 only — fast dashboard endpoint) ──────────

_smart_reco_cache: Dict[str, Any] = {}
_smart_reco_lock = threading.Lock()


@app.post("/api/smart-recommendations")
async def run_smart_recommendations_endpoint(
    product_id: str = Query(default=""),
    customer_id: str = Query(default=""),
    cart_filter: str = Query(default=""),
) -> Dict[str, Any]:
    """
    Run ONLY the Business & Marketing Advisor agent on the live KPI snapshot.
    Faster than the full pipeline — intended for inline dashboard usage.
    """
    loop = asyncio.get_event_loop()

    def _run() -> Dict[str, Any]:
        try:
            from agents import run_smart_recommendations  # lazy import
        except ImportError as exc:
            return {"error": f"agents module not found: {exc}"}

        snapshot = build_payload(
            product_id=product_id,
            customer_id=customer_id,
            cart_filter=cart_filter,
        )
        result = run_smart_recommendations(snapshot)
        with _smart_reco_lock:
            _smart_reco_cache.clear()
            _smart_reco_cache.update(result)
        return result

    try:
        result = await loop.run_in_executor(_agent_executor, _run)
        return result
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/smart-recommendations/last")
def get_last_smart_recommendations() -> Dict[str, Any]:
    """Return cached smart recommendations (or empty if none triggered yet)."""
    with _smart_reco_lock:
        if not _smart_reco_cache:
            return {"status": "no_reco_yet", "message": "Lance via POST /api/smart-recommendations"}
        return dict(_smart_reco_cache)


@app.websocket("/ws/kpis")
async def kpi_socket(websocket: WebSocket) -> None:
    await websocket.accept()
    product_id = websocket.query_params.get("product_id", "")
    customer_id = websocket.query_params.get("customer_id", "")
    cart_filter = websocket.query_params.get("cart_filter", "")
    try:
        while True:
            await websocket.send_json(
                build_payload(product_id=product_id, customer_id=customer_id, cart_filter=cart_filter)
            )
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
