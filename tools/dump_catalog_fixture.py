"""把後端服務目錄／題組定義輸出成前端測試 fixture。

前端測試不手寫題組定義——一律由此腳本從後端產生，確保 fixture 不會悄悄與後端漂移。
用法：`uv run python tools/dump_catalog_fixture.py`
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.forms import service_catalog  # noqa: E402
from core.forms.dto import form_to_dict, service_to_dict  # noqa: E402
from core.insights.today import build_briefing  # noqa: E402
from core.services import InsightsService  # noqa: E402

# 與 api.app.DEMO_TODAY 一致，日期題的絕對範圍才對得上
DEMO_TODAY = date(2026, 7, 25)
OUT = Path(__file__).resolve().parents[1] / "web" / "app" / "tests" / "fixtures" / "catalog.generated.ts"

HEADER = """/**
 * 由後端產生的服務目錄 fixture——**請勿手改**。
 *
 * 重新產生：`uv run python tools/dump_catalog_fixture.py`
 * 來源：core/forms/service_catalog.py + core/forms/dto.py（展示基準日 2026-07-25）
 */
import type { BehaviorSummary, BriefingItem, Recommendation, TrailEvent } from '@/api/insightsClient'
import type { CatalogService } from '@/api/serviceCatalogClient'
import type { ServiceFormDefinition } from '@/domain/serviceIntake'

"""


def main() -> None:
    services = [service_to_dict(service) for service in service_catalog.list_services()]
    forms = {}
    for service in services:
        form = service_catalog.get_service_form(service["id"])
        assert form is not None, service["id"]
        forms[service["id"]] = form_to_dict(form, today=DEMO_TODAY)

    insights = InsightsService(today=DEMO_TODAY)
    # 今日摘要用展示帳號的真實推薦算出來；沒有諮詢單／團購時只會有 suggestion 類
    briefing = build_briefing(
        account_id=insights.summary()["accountId"],
        inquiries=[],
        campaigns=[],
        today=DEMO_TODAY,
    )
    body = (
        "export const catalogServices: CatalogService[] = "
        + json.dumps(services, ensure_ascii=False, indent=2)
        + "\n\nexport const catalogForms: Record<string, ServiceFormDefinition> = "
        + json.dumps(forms, ensure_ascii=False, indent=2)
        + " as unknown as Record<string, ServiceFormDefinition>\n"
        + "\nexport const insightSummary: BehaviorSummary = "
        + json.dumps(insights.summary(), ensure_ascii=False, indent=2)
        + " as unknown as BehaviorSummary\n"
        + "\nexport const insightRecommendations: Recommendation[] = "
        + json.dumps(insights.recommendations(), ensure_ascii=False, indent=2)
        + " as unknown as Recommendation[]\n"
        + "\nexport const insightTrail: TrailEvent[] = "
        + json.dumps(insights.trail(), ensure_ascii=False, indent=2)
        + " as unknown as TrailEvent[]\n"
        + "\nexport const todayBriefing: BriefingItem[] = "
        + json.dumps([item.to_dict() for item in briefing], ensure_ascii=False, indent=2)
        + " as unknown as BriefingItem[]\n"
        + "\nexport const insightAccounts = "
        + json.dumps(insights.accounts(), ensure_ascii=False, indent=2)
        + "\n"
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(HEADER + body, encoding="utf-8")
    print(f"wrote {OUT.relative_to(Path.cwd())} ({len(services)} services, insights included)")


if __name__ == "__main__":
    main()
