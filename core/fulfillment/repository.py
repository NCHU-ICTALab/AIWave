from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


class FulfillmentError(ValueError):
    pass


class FulfillmentConflict(FulfillmentError):
    pass


BOOKING_TRANSITIONS = {
    "pending_provider": {"confirmed", "rejected", "cancelled"},
    "confirmed": {"in_service", "cancelled"},
    "in_service": {"completed", "exception"},
    "exception": {"in_service", "cancelled"},
}

ORDER_TRANSITIONS = {
    "placed": {"accepted", "cancelled", "payment_failed"},
    # 付款失敗不是死狀態:重新付款成功回到 placed,或由會員取消
    "payment_failed": {"placed", "cancelled"},
    "accepted": {"preparing", "cancelled"},
    "preparing": {"shipped", "ready_for_pickup", "cancelled"},
    # 店到店/門市取貨:出貨(運送中)後可「到店」再由取件人完成
    "shipped": {"delivered", "ready_for_pickup", "exception"},
    "ready_for_pickup": {"delivered", "exception"},
    "exception": {"shipped", "ready_for_pickup", "cancelled"},
}


class SqliteFulfillmentRepository:
    """Separate booking and commerce aggregates sharing only StatusEvent."""

    def __init__(
        self,
        path: str | Path,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _timestamp(self) -> str:
        value = self._now()
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS bookings (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    location_id TEXT NOT NULL,
                    offering_id TEXT NOT NULL,
                    resource_id TEXT,
                    slot_id TEXT NOT NULL,
                    starts_at TEXT NOT NULL,
                    ends_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_bookings_owner
                    ON bookings(demo_workspace_id,workspace_id,account_id,created_at);
                CREATE TABLE IF NOT EXISTS commerce_orders (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    account_id TEXT NOT NULL,
                    provider_id TEXT NOT NULL,
                    currency TEXT NOT NULL CHECK(currency='TWD'),
                    subtotal INTEGER NOT NULL CHECK(subtotal>=0),
                    discount INTEGER NOT NULL CHECK(discount>=0),
                    total INTEGER NOT NULL CHECK(total>=0),
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_commerce_orders_owner
                    ON commerce_orders(demo_workspace_id,workspace_id,account_id,created_at);
                CREATE TABLE IF NOT EXISTS commerce_order_items (
                    order_id TEXT NOT NULL,
                    line_no INTEGER NOT NULL,
                    offering_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK(quantity>0),
                    unit_price INTEGER NOT NULL CHECK(unit_price>=0),
                    amount INTEGER NOT NULL CHECK(amount>=0),
                    PRIMARY KEY(order_id,line_no),
                    FOREIGN KEY(order_id) REFERENCES commerce_orders(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS status_events (
                    id TEXT PRIMARY KEY,
                    demo_workspace_id TEXT NOT NULL,
                    workspace_id TEXT NOT NULL,
                    subject_type TEXT NOT NULL CHECK(subject_type IN ('booking','commerce_order')),
                    subject_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    from_status TEXT,
                    to_status TEXT NOT NULL,
                    actor_account_id TEXT NOT NULL,
                    actor_role TEXT NOT NULL,
                    note TEXT,
                    metadata_json TEXT NOT NULL,
                    idempotency_key TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    UNIQUE(demo_workspace_id,subject_type,subject_id,idempotency_key)
                );
                CREATE INDEX IF NOT EXISTS ix_status_events_subject
                    ON status_events(demo_workspace_id,subject_type,subject_id,occurred_at);
                CREATE TABLE IF NOT EXISTS booking_reschedule_requests (
                    id TEXT PRIMARY KEY,
                    booking_id TEXT NOT NULL,
                    requested_slot_id TEXT NOT NULL,
                    requested_starts_at TEXT NOT NULL,
                    requested_ends_at TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL CHECK(status IN ('pending','accepted','rejected','cancelled')),
                    requested_by TEXT NOT NULL,
                    reviewed_by TEXT,
                    idempotency_key TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(booking_id,idempotency_key),
                    FOREIGN KEY(booking_id) REFERENCES bookings(id) ON DELETE CASCADE
                );
                """
            )
            booking_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(bookings)")
            }
            if "details" not in booking_columns:
                connection.execute("ALTER TABLE bookings ADD COLUMN details TEXT")

    @staticmethod
    def _event(row: sqlite3.Row) -> dict:
        return {
            "id": row["id"], "type": row["event_type"],
            "fromStatus": row["from_status"], "toStatus": row["to_status"],
            "actorAccountId": row["actor_account_id"], "actorRole": row["actor_role"],
            "note": row["note"], "metadata": json.loads(row["metadata_json"]),
            "occurredAt": row["occurred_at"],
        }

    def _events(self, connection: sqlite3.Connection, *, demo_workspace_id: str, subject_type: str, subject_id: str) -> list[dict]:
        rows = connection.execute(
            """SELECT * FROM status_events WHERE demo_workspace_id=? AND subject_type=? AND subject_id=?
               ORDER BY occurred_at,rowid""",
            (demo_workspace_id, subject_type, subject_id),
        ).fetchall()
        return [self._event(row) for row in rows]

    def _append_event(
        self,
        connection: sqlite3.Connection,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        subject_type: str,
        subject_id: str,
        event_type: str,
        from_status: str | None,
        to_status: str,
        actor_account_id: str,
        actor_role: str,
        idempotency_key: str,
        note: str | None = None,
        metadata: dict | None = None,
    ) -> bool:
        cursor = connection.execute(
            """INSERT OR IGNORE INTO status_events
               (id,demo_workspace_id,workspace_id,subject_type,subject_id,event_type,from_status,to_status,
                actor_account_id,actor_role,note,metadata_json,idempotency_key,occurred_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                f"event-{uuid4().hex[:16]}", demo_workspace_id, workspace_id,
                subject_type, subject_id, event_type, from_status, to_status,
                actor_account_id, actor_role, note,
                json.dumps(metadata or {}, ensure_ascii=False), idempotency_key, self._timestamp(),
            ),
        )
        return cursor.rowcount == 1

    def create_booking(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        provider_id: str,
        location_id: str,
        offering_id: str,
        resource_id: str | None,
        slot_id: str,
        starts_at: str,
        ends_at: str,
        idempotency_key: str,
        details: dict | None = None,
    ) -> dict:
        if not all(value.strip() for value in (provider_id, location_id, offering_id, slot_id, starts_at, ends_at, idempotency_key)):
            raise FulfillmentError("預約的店家、據點、方案、時段與 Idempotency-Key 都不可空白")
        booking_id = f"booking-{uuid4().hex[:16]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM bookings WHERE demo_workspace_id=? AND idempotency_key=?",
                (demo_workspace_id, idempotency_key),
            ).fetchone()
            if existing:
                record = self.get_booking(
                    existing["id"], demo_workspace_id=demo_workspace_id,
                    workspace_id=workspace_id, account_id=account_id,
                )
                record["idempotentReplay"] = True
                return record
            connection.execute(
                """INSERT INTO bookings
                   (id,demo_workspace_id,workspace_id,account_id,provider_id,location_id,offering_id,
                    resource_id,slot_id,starts_at,ends_at,status,version,idempotency_key,created_at,updated_at,details)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'pending_provider',1,?,?,?,?)""",
                (
                    booking_id, demo_workspace_id, workspace_id, account_id, provider_id, location_id,
                    offering_id, resource_id, slot_id, starts_at, ends_at, idempotency_key, timestamp, timestamp,
                    json.dumps(details, ensure_ascii=False) if details else None,
                ),
            )
            self._append_event(
                connection,
                demo_workspace_id=demo_workspace_id, workspace_id=workspace_id,
                subject_type="booking", subject_id=booking_id, event_type="booking_created",
                from_status=None, to_status="pending_provider", actor_account_id=account_id,
                actor_role="member", idempotency_key=f"{idempotency_key}:event",
            )
            record = self._booking_record(connection, booking_id)
            record["idempotentReplay"] = False
            return record

    def find_booking_by_idempotency(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        idempotency_key: str,
    ) -> dict | None:
        with self._connect() as connection:
            row = connection.execute(
                """SELECT id FROM bookings WHERE demo_workspace_id=? AND workspace_id=?
                   AND account_id=? AND idempotency_key=?""",
                (demo_workspace_id, workspace_id, account_id, idempotency_key),
            ).fetchone()
            return None if row is None else self._booking_record(connection, row["id"])

    def _booking_record(self, connection: sqlite3.Connection, booking_id: str) -> dict:
        row = connection.execute("SELECT * FROM bookings WHERE id=?", (booking_id,)).fetchone()
        if row is None:
            raise FulfillmentError("查無預約")
        return {
            "id": row["id"], "demoWorkspaceId": row["demo_workspace_id"],
            "workspaceId": row["workspace_id"], "accountId": row["account_id"],
            "providerId": row["provider_id"], "locationId": row["location_id"],
            "offeringId": row["offering_id"], "resourceId": row["resource_id"],
            "slotId": row["slot_id"], "startsAt": row["starts_at"], "endsAt": row["ends_at"],
            "status": row["status"], "version": row["version"],
            # 履約必要欄位(個資最小化,由 submit 時依 domain 欄位過濾)
            "details": json.loads(row["details"]) if row["details"] else None,
            "events": self._events(
                connection, demo_workspace_id=row["demo_workspace_id"],
                subject_type="booking", subject_id=booking_id,
            ),
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    def get_booking(
        self,
        booking_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str | None = None,
        provider_id: str | None = None,
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM bookings WHERE id=? AND demo_workspace_id=?",
                (booking_id, demo_workspace_id),
            ).fetchone()
            if row is None:
                raise FulfillmentError("查無預約")
            owner_ok = account_id is not None and row["workspace_id"] == workspace_id and row["account_id"] == account_id
            provider_ok = provider_id is not None and row["provider_id"] == provider_id
            if not (owner_ok or provider_ok):
                raise FulfillmentError("查無預約")
            return self._booking_record(connection, booking_id)

    def list_bookings(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str | None = None,
        account_id: str | None = None,
        provider_id: str | None = None,
    ) -> list[dict]:
        if provider_id is None and (workspace_id is None or account_id is None):
            raise FulfillmentError("查詢預約需要會員工作空間或合作方身分")
        clauses, values = ["demo_workspace_id=?"], [demo_workspace_id]
        if provider_id is not None:
            clauses.append("provider_id=?")
            values.append(provider_id)
        else:
            clauses.extend(["workspace_id=?", "account_id=?"])
            values.extend([workspace_id, account_id])
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT id FROM bookings WHERE {' AND '.join(clauses)} ORDER BY created_at DESC,id",
                values,
            ).fetchall()
            return [self._booking_record(connection, row["id"]) for row in rows]

    def transition_booking(
        self,
        booking_id: str,
        *,
        demo_workspace_id: str,
        provider_id: str,
        expected_version: int,
        to_status: str,
        actor_account_id: str,
        idempotency_key: str,
        note: str | None = None,
        actor_role: str = "partner_staff",
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM bookings WHERE id=? AND demo_workspace_id=? AND provider_id=?",
                (booking_id, demo_workspace_id, provider_id),
            ).fetchone()
            if row is None:
                raise FulfillmentError("查無預約")
            existing_event = connection.execute(
                """SELECT 1 FROM status_events WHERE demo_workspace_id=? AND subject_type='booking'
                   AND subject_id=? AND idempotency_key=?""",
                (demo_workspace_id, booking_id, idempotency_key),
            ).fetchone()
            if existing_event:
                record = self._booking_record(connection, booking_id)
                record["idempotentReplay"] = True
                return record
            if row["version"] != expected_version:
                raise FulfillmentConflict("預約版本已更新，請重新載入")
            if to_status not in BOOKING_TRANSITIONS.get(row["status"], set()):
                raise FulfillmentConflict(f"預約不可由 {row['status']} 變更為 {to_status}")
            connection.execute(
                "UPDATE bookings SET status=?,version=version+1,updated_at=? WHERE id=?",
                (to_status, self._timestamp(), booking_id),
            )
            self._append_event(
                connection,
                demo_workspace_id=demo_workspace_id, workspace_id=row["workspace_id"],
                subject_type="booking", subject_id=booking_id, event_type=f"booking_{to_status}",
                from_status=row["status"], to_status=to_status, actor_account_id=actor_account_id,
                actor_role=actor_role, idempotency_key=idempotency_key, note=note,
            )
            record = self._booking_record(connection, booking_id)
            record["idempotentReplay"] = False
            return record

    def request_reschedule(
        self,
        booking_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        slot_id: str,
        starts_at: str,
        ends_at: str,
        reason: str | None,
        idempotency_key: str,
    ) -> dict:
        booking = self.get_booking(
            booking_id, demo_workspace_id=demo_workspace_id,
            workspace_id=workspace_id, account_id=account_id,
        )
        if booking["status"] not in {"pending_provider", "confirmed"}:
            raise FulfillmentConflict("目前預約狀態不可申請改期")
        request_id = f"reschedule-{uuid4().hex[:16]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM booking_reschedule_requests WHERE booking_id=? AND idempotency_key=?",
                (booking_id, idempotency_key),
            ).fetchone()
            if existing:
                return {**dict(existing), "idempotentReplay": True}
            connection.execute(
                """INSERT INTO booking_reschedule_requests
                   (id,booking_id,requested_slot_id,requested_starts_at,requested_ends_at,reason,status,
                    requested_by,idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,'pending',?,?,?,?)""",
                (
                    request_id, booking_id, slot_id, starts_at, ends_at, reason,
                    account_id, idempotency_key, timestamp, timestamp,
                ),
            )
            return {
                "id": request_id, "bookingId": booking_id, "requestedSlotId": slot_id,
                "requestedStartsAt": starts_at, "requestedEndsAt": ends_at,
                "status": "pending", "idempotentReplay": False,
            }

    def review_reschedule(
        self,
        request_id: str,
        *,
        demo_workspace_id: str,
        provider_id: str,
        actor_account_id: str,
        accept: bool,
        idempotency_key: str,
    ) -> dict:
        with self._connect() as connection:
            request = connection.execute(
                """SELECT r.*,b.provider_id,b.workspace_id,b.version,b.status booking_status
                   FROM booking_reschedule_requests r JOIN bookings b ON b.id=r.booking_id
                   WHERE r.id=? AND b.demo_workspace_id=? AND b.provider_id=?""",
                (request_id, demo_workspace_id, provider_id),
            ).fetchone()
            if request is None:
                raise FulfillmentError("查無改期申請")
            desired = "accepted" if accept else "rejected"
            if request["status"] != "pending":
                if request["status"] != desired:
                    raise FulfillmentConflict("改期申請已處理")
                return {"id": request_id, "status": desired, "idempotentReplay": True}
            timestamp = self._timestamp()
            connection.execute(
                """UPDATE booking_reschedule_requests
                   SET status=?,reviewed_by=?,updated_at=? WHERE id=?""",
                (desired, actor_account_id, timestamp, request_id),
            )
            if accept:
                connection.execute(
                    """UPDATE bookings SET slot_id=?,starts_at=?,ends_at=?,version=version+1,updated_at=?
                       WHERE id=?""",
                    (
                        request["requested_slot_id"], request["requested_starts_at"],
                        request["requested_ends_at"], timestamp, request["booking_id"],
                    ),
                )
                self._append_event(
                    connection,
                    demo_workspace_id=demo_workspace_id, workspace_id=request["workspace_id"],
                    subject_type="booking", subject_id=request["booking_id"], event_type="booking_rescheduled",
                    from_status=request["booking_status"], to_status=request["booking_status"],
                    actor_account_id=actor_account_id, actor_role="partner_staff",
                    idempotency_key=idempotency_key,
                    metadata={
                        "slotId": request["requested_slot_id"],
                        "startsAt": request["requested_starts_at"],
                        "endsAt": request["requested_ends_at"],
                    },
                )
            return {"id": request_id, "bookingId": request["booking_id"], "status": desired, "idempotentReplay": False}

    def create_order(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str,
        provider_id: str,
        items: list[dict],
        discount: int,
        idempotency_key: str,
    ) -> dict:
        if not items:
            raise FulfillmentError("購物訂單至少需要一個品項")
        normalized = []
        for item in items:
            quantity, unit_price = int(item["quantity"]), int(item["unitPrice"])
            if quantity <= 0 or unit_price < 0:
                raise FulfillmentError("品項數量與價格不合法")
            normalized.append({**item, "quantity": quantity, "unitPrice": unit_price, "amount": quantity * unit_price})
        subtotal = sum(item["amount"] for item in normalized)
        if discount < 0 or discount > subtotal:
            raise FulfillmentError("折扣金額不合法")
        order_id = f"order-{uuid4().hex[:16]}"
        timestamp = self._timestamp()
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT id FROM commerce_orders WHERE demo_workspace_id=? AND idempotency_key=?",
                (demo_workspace_id, idempotency_key),
            ).fetchone()
            if existing:
                record = self.get_order(
                    existing["id"], demo_workspace_id=demo_workspace_id,
                    workspace_id=workspace_id, account_id=account_id,
                )
                record["idempotentReplay"] = True
                return record
            connection.execute(
                """INSERT INTO commerce_orders
                   (id,demo_workspace_id,workspace_id,account_id,provider_id,currency,subtotal,discount,total,
                    status,version,idempotency_key,created_at,updated_at)
                   VALUES (?,?,?,?,?,'TWD',?,?,?,'placed',1,?,?,?)""",
                (
                    order_id, demo_workspace_id, workspace_id, account_id, provider_id,
                    subtotal, discount, subtotal - discount, idempotency_key, timestamp, timestamp,
                ),
            )
            for index, item in enumerate(normalized, 1):
                connection.execute(
                    """INSERT INTO commerce_order_items
                       (order_id,line_no,offering_id,name,quantity,unit_price,amount)
                       VALUES (?,?,?,?,?,?,?)""",
                    (
                        order_id, index, item["offeringId"], item["name"],
                        item["quantity"], item["unitPrice"], item["amount"],
                    ),
                )
            self._append_event(
                connection,
                demo_workspace_id=demo_workspace_id, workspace_id=workspace_id,
                subject_type="commerce_order", subject_id=order_id, event_type="order_placed",
                from_status=None, to_status="placed", actor_account_id=account_id,
                actor_role="member", idempotency_key=f"{idempotency_key}:event",
            )
            record = self._order_record(connection, order_id)
            record["idempotentReplay"] = False
            return record

    def _order_record(self, connection: sqlite3.Connection, order_id: str) -> dict:
        row = connection.execute("SELECT * FROM commerce_orders WHERE id=?", (order_id,)).fetchone()
        if row is None:
            raise FulfillmentError("查無購物訂單")
        items = connection.execute(
            "SELECT * FROM commerce_order_items WHERE order_id=? ORDER BY line_no", (order_id,),
        ).fetchall()
        return {
            "id": row["id"], "demoWorkspaceId": row["demo_workspace_id"],
            "workspaceId": row["workspace_id"], "accountId": row["account_id"],
            "providerId": row["provider_id"], "currency": row["currency"],
            "subtotal": row["subtotal"], "discount": row["discount"], "total": row["total"],
            "status": row["status"], "version": row["version"],
            "items": [
                {
                    "offeringId": item["offering_id"], "name": item["name"],
                    "quantity": item["quantity"], "unitPrice": item["unit_price"], "amount": item["amount"],
                }
                for item in items
            ],
            "events": self._events(
                connection, demo_workspace_id=row["demo_workspace_id"],
                subject_type="commerce_order", subject_id=order_id,
            ),
            "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        }

    def get_order(
        self,
        order_id: str,
        *,
        demo_workspace_id: str,
        workspace_id: str,
        account_id: str | None = None,
        provider_id: str | None = None,
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commerce_orders WHERE id=? AND demo_workspace_id=?", (order_id, demo_workspace_id),
            ).fetchone()
            if row is None:
                raise FulfillmentError("查無購物訂單")
            owner_ok = account_id is not None and row["workspace_id"] == workspace_id and row["account_id"] == account_id
            provider_ok = provider_id is not None and row["provider_id"] == provider_id
            if not (owner_ok or provider_ok):
                raise FulfillmentError("查無購物訂單")
            return self._order_record(connection, order_id)

    def list_orders(
        self,
        *,
        demo_workspace_id: str,
        workspace_id: str | None = None,
        account_id: str | None = None,
        provider_id: str | None = None,
    ) -> list[dict]:
        if provider_id is None and (workspace_id is None or account_id is None):
            raise FulfillmentError("查詢訂單需要會員工作空間或合作方身分")
        clauses, values = ["demo_workspace_id=?"], [demo_workspace_id]
        if provider_id is not None:
            clauses.append("provider_id=?")
            values.append(provider_id)
        else:
            clauses.extend(["workspace_id=?", "account_id=?"])
            values.extend([workspace_id, account_id])
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT id FROM commerce_orders WHERE {' AND '.join(clauses)} ORDER BY created_at DESC,id",
                values,
            ).fetchall()
            return [self._order_record(connection, row["id"]) for row in rows]

    def transition_order(
        self,
        order_id: str,
        *,
        demo_workspace_id: str,
        provider_id: str,
        expected_version: int,
        to_status: str,
        actor_account_id: str,
        idempotency_key: str,
        note: str | None = None,
        actor_role: str = "partner_staff",
    ) -> dict:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM commerce_orders WHERE id=? AND demo_workspace_id=? AND provider_id=?",
                (order_id, demo_workspace_id, provider_id),
            ).fetchone()
            if row is None:
                raise FulfillmentError("查無購物訂單")
            existing = connection.execute(
                """SELECT 1 FROM status_events WHERE demo_workspace_id=? AND subject_type='commerce_order'
                   AND subject_id=? AND idempotency_key=?""",
                (demo_workspace_id, order_id, idempotency_key),
            ).fetchone()
            if existing:
                record = self._order_record(connection, order_id)
                record["idempotentReplay"] = True
                return record
            if row["version"] != expected_version:
                raise FulfillmentConflict("訂單版本已更新，請重新載入")
            if to_status not in ORDER_TRANSITIONS.get(row["status"], set()):
                raise FulfillmentConflict(f"訂單不可由 {row['status']} 變更為 {to_status}")
            connection.execute(
                "UPDATE commerce_orders SET status=?,version=version+1,updated_at=? WHERE id=?",
                (to_status, self._timestamp(), order_id),
            )
            self._append_event(
                connection,
                demo_workspace_id=demo_workspace_id, workspace_id=row["workspace_id"],
                subject_type="commerce_order", subject_id=order_id, event_type=f"order_{to_status}",
                from_status=row["status"], to_status=to_status, actor_account_id=actor_account_id,
                actor_role=actor_role, idempotency_key=idempotency_key, note=note,
            )
            record = self._order_record(connection, order_id)
            record["idempotentReplay"] = False
            return record
