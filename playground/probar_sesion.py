from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)

    context = browser.new_context(
        storage_state="estado_siaf.json"
    )

    page = context.new_page()

    page.goto("https://apps.mef.gob.pe/websiaf/")

    page.wait_for_timeout(5000)

    print(page.title())

    input("¿Sigue autenticado?")

    browser.close()