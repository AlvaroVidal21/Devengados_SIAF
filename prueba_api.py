from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        storage_state="estado_siaf.json"
    )

    response = context.request.get(
        "https://apps.mef.gob.pe/v1/siaf-services/devengado/devengados",
        params={
            "anio": 2026,
            "expediente": 111,
            "page": 0,
            "page_size": 10,
            "sort": "-"
        }
    )

    print(response.status)
    print(response.text())

    browser.close()