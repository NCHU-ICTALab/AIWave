from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent
URL = (ROOT / "index.html").as_uri()


def expect_text(page, selector: str, text: str) -> None:
    actual = page.locator(selector).inner_text()
    assert text in actual, f"{selector}: expected {text!r}, got {actual!r}"


def run() -> None:
    errors: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.on("pageerror", lambda error: errors.append(f"pageerror: {error}"))
        page.on(
            "console",
            lambda message: errors.append(f"console: {message.text}")
            if message.type == "error"
            else None,
        )

        page.goto(URL)
        page.wait_for_timeout(350)

        # Flow A: recommendation feedback -> undo -> discount preview -> order.
        page.locator("#recommendation-feedback").click()
        assert page.locator("#recommendation-feedback-note").is_visible()
        page.locator("#recommendation-inline-undo").click()
        assert not page.locator("#recommendation-feedback-note").is_visible()
        page.locator('[data-route="services"]').first.click()
        page.locator("#service-continue").click()
        expect_text(page, "#modal-title", "確認商城購物")
        page.locator("#modal-confirm").click()
        expect_text(page, "#demo-order-status", "已成立")
        expect_text(page, "#demo-order-meta", "OP-0724-001")

        # Flow B: Copilot draft -> manager confirmation -> quote -> status return.
        page.locator('[data-route="community"]').first.click()
        page.locator("#draft-campaign").click()
        assert page.locator("#copilot-layer").is_visible()
        page.locator("#copilot-action-button").click()
        page.wait_for_timeout(300)
        expect_text(page, "#campaign-draft", "草稿已產生")
        page.locator("#publish-campaign").click()
        page.locator("#modal-confirm").click()
        expect_text(page, "#campaign-state", "活動已開放")

        page.locator('[data-route="vendor"]').first.click()
        page.locator("#create-quote").click()
        page.locator("#modal-confirm").click()
        expect_text(page, "#vendor-queue-status", "已報價")
        page.locator("#update-fulfillment").click()
        expect_text(page, "#vendor-fulfillment", "已排程")
        page.locator('[data-route="community"]').first.click()
        expect_text(page, "#community-quote", "已排程")

        # Platform proof: one contract reaches four channels.
        page.locator('[data-route="platform"]').first.click()
        page.locator("#contract-test").click()
        page.wait_for_timeout(850)
        expect_text(page, "#connector-result", "4/4 通路可共用")
        assert page.locator('[data-test-cell].is-valid').count() == 2

        # Mobile service search keeps the five-column familiar scan and filters.
        page.set_viewport_size({"width": 390, "height": 844})
        page.goto("about:blank")
        page.goto(f"{URL}#services")
        page.wait_for_timeout(350)
        page.locator("#service-query").fill("冷氣")
        expect_text(page, "#search-result-note", "找到 1 項")
        assert page.locator(".catalog-service:not([hidden])").count() == 1
        page.locator('.catalog-service[data-service="冷氣清洗"]').click()
        expect_text(page, "#selected-service-title", "冷氣清洗")

        page.screenshot(path=ROOT / "screenshots" / "interaction-final-mobile.png")
        browser.close()

    assert not errors, "\n".join(errors)
    print("PASS: recommendation, order, community, vendor, platform, and mobile search")


if __name__ == "__main__":
    run()
