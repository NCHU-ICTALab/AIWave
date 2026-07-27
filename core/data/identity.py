"""行為指紋：把散落在多個帳號的訂單認回同一個人。

這正是 [CONTEXT.md](../../CONTEXT.md) 定義的**行為指紋**（identity resolution），
與**行為軌跡**（解析後依時間排出的事件序列）是兩件事。

官方 `mms_order_record` 每一列都帶 `member_name_hash`／`member_phone_hash`／
`member_email_hash`。實測這些雜湊**真的跨帳號重複**——同一個人在不同通路下單，
被記成不同的 `inbr_account_id`：

    member_email_hash xLzkAem… → 019eee3f、019a52d3、019ef24a
    member_name_hash  dR79Ty0… → 019eee3f、019a52d3
    member_phone_hash A0PgPpt… → 019eee3f、019ef24a

所以合併不是我們編的，是官方資料本身就指出來的。用聯集尋找（union-find）
把共用任一雜湊的帳號併成一個身分：10 個帳號 → 8 個身分，其中一位橫跨 5 種服務。

**只用雜湊欄位，不用明文。** 明文 `member_name`／`member_phone` 在範例資料裡是加密
位元組，逐列不同（33 個相異值對 99 列），拿來比對只會得到「每列都是不同人」。
雜湊欄位才是官方設計來做這件事的。
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache

from .official_source import RAW_DATA, load_tables

_ORDERS = RAW_DATA / "order_record範例資料.json"

#: 官方設計來做身分解析的欄位。明文欄位刻意不列——見模組說明。
LINK_FIELDS = ("member_name_hash", "member_phone_hash", "member_email_hash")


@dataclass(frozen=True)
class ResolvedIdentity:
    """一個經行為指紋解析出來的人。"""

    id: str
    #: 被認回同一人的官方帳號（至少一個）
    account_ids: tuple[str, ...]
    #: 促成合併的雜湊欄位；單一帳號時為空
    linked_by: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_merged(self) -> bool:
        return len(self.account_ids) > 1

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "accountIds": list(self.account_ids),
            "linkedBy": list(self.linked_by),
            "isMerged": self.is_merged,
            "resolvedBy": "member_hash",
        }


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[str, str] = {}

    def add(self, item: str) -> None:
        self._parent.setdefault(item, item)

    def find(self, item: str) -> str:
        self.add(item)
        root = item
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[item] != root:   # 路徑壓縮
            self._parent[item], item = root, self._parent[item]
        return root

    def union(self, a: str, b: str) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self._parent[root_a] = root_b


@lru_cache(maxsize=1)
def resolve_identities() -> tuple[ResolvedIdentity, ...]:
    """依官方雜湊欄位把帳號併成身分，依帳號數與代碼排序（結果必須可重現）。"""
    rows = load_tables(_ORDERS).get("mms_order_record", [])
    union = _UnionFind()
    #: root → 促成合併的欄位
    evidence: dict[str, set[str]] = defaultdict(set)

    for row in rows:
        account_id = row.get("inbr_account_id")
        if account_id:
            union.add(str(account_id))

    for field_name in LINK_FIELDS:
        by_hash: dict[str, list[str]] = defaultdict(list)
        for row in rows:
            value, account_id = row.get(field_name), row.get("inbr_account_id")
            if value in (None, "", "null") or not account_id:
                continue
            accounts = by_hash[str(value)]
            if str(account_id) not in accounts:
                accounts.append(str(account_id))
        for accounts in by_hash.values():
            if len(accounts) < 2:
                continue
            for other in accounts[1:]:
                union.union(accounts[0], other)
            evidence[union.find(accounts[0])].add(field_name)

    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        account_id = row.get("inbr_account_id")
        if not account_id:
            continue
        root = union.find(str(account_id))
        if str(account_id) not in grouped[root]:
            grouped[root].append(str(account_id))

    identities = [
        ResolvedIdentity(
            # 用排序後的第一個帳號當 id，讓結果與讀取順序無關
            id=sorted(accounts)[0],
            account_ids=tuple(sorted(accounts)),
            linked_by=tuple(sorted(evidence.get(root, ()))),
        )
        for root, accounts in grouped.items()
    ]
    identities.sort(key=lambda identity: (-len(identity.account_ids), identity.id))
    return tuple(identities)


@lru_cache(maxsize=1)
def _account_to_identity() -> dict[str, str]:
    return {
        account_id: identity.id
        for identity in resolve_identities()
        for account_id in identity.account_ids
    }


def identity_of(account_id: str) -> str:
    """該帳號屬於哪個身分；沒解析到就是它自己。"""
    return _account_to_identity().get(account_id, account_id)


def accounts_of(identity_id: str) -> tuple[str, ...]:
    """一個身分底下的所有官方帳號。"""
    for identity in resolve_identities():
        if identity.id == identity_id:
            return identity.account_ids
    return (identity_id,)
