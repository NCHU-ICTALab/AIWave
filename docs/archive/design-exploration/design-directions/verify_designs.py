"""Capture all UI directions at desktop and mobile preview sizes."""

import json
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "screenshots" / "directions"
THEMES = ("grid", "warm", "pulse", "data", "calm", "clinical", "bridge", "hybrid")
COLORWAYS = ("teal", "cobalt", "forest", "brick", "indigo")
HYBRID_TONES = ("bridge", "grove", "mist", "clay")


def main() -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report = {"console_errors": [], "interaction_checks": [], "screens": []}

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
        page.on("console", lambda message: report["console_errors"].append(message.text) if message.type == "error" else None)
        page.goto((ROOT / "index.html").as_uri(), wait_until="networkidle")

        page.locator("[data-feedback]").click()
        report["interaction_checks"].append(
            {"action": "recommendation feedback", "toast_visible": page.locator(".toast").is_visible()}
        )
        page.locator("[data-undo]").click()
        report["interaction_checks"].append(
            {"action": "undo feedback", "toast_hidden": page.locator(".toast").is_hidden()}
        )

        for theme in THEMES:
            page.locator(f'[data-theme="{theme}"]').click()
            for device in ("desktop", "mobile"):
                page.locator(f'button[data-device="{device}"]').click()
                page.wait_for_timeout(150)
                page.locator("#app-preview").evaluate("el => { el.scrollTop = 0; el.scrollLeft = 0; }")
                stage = page.locator(".browser-stage")
                output = OUTPUT / f"{theme}-{device}.png"
                stage.screenshot(path=str(output))
                overflow = page.locator("#app-preview").evaluate(
                    "el => ({clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight})"
                )
                report["screens"].append({"theme": theme, "device": device, "file": output.name, "overflow": overflow})

        page.locator('[data-theme="clinical"]').click()
        for colorway in COLORWAYS:
            page.locator(f'button[data-colorway="{colorway}"]').click()
            for device in ("desktop", "mobile"):
                page.locator(f'button[data-device="{device}"]').click()
                page.wait_for_timeout(150)
                page.locator("#app-preview").evaluate("el => { el.scrollTop = 0; el.scrollLeft = 0; }")
                stage = page.locator(".browser-stage")
                output = OUTPUT / f"clinical-{colorway}-{device}.png"
                stage.screenshot(path=str(output))
                overflow = page.locator("#app-preview").evaluate(
                    "el => ({clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight})"
                )
                report["screens"].append({"theme":"clinical","colorway":colorway,"device":device,"file":output.name,"overflow":overflow})

        page.locator('[data-theme="hybrid"]').click()
        for tone in HYBRID_TONES:
            page.locator(f'button[data-hybrid-tone="{tone}"]').click()
            for device in ("desktop", "mobile"):
                page.locator(f'button[data-device="{device}"]').click()
                page.wait_for_timeout(150)
                page.locator("#app-preview").evaluate("el => { el.scrollTop = 0; el.scrollLeft = 0; }")
                stage = page.locator(".browser-stage")
                output = OUTPUT / f"hybrid-{tone}-{device}.png"
                stage.screenshot(path=str(output))
                overflow = page.locator("#app-preview").evaluate(
                    "el => ({clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight})"
                )
                report["screens"].append({"theme":"hybrid","tone":tone,"device":device,"file":output.name,"overflow":overflow})

        browser.close()

    (OUTPUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
