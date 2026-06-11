from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(storage_state="estado_siaf.json")
    page = context.new_page()

    page.goto("https://apps.mef.gob.pe/websiaf/")
    page.wait_for_timeout(5000)

    data = page.evaluate("""
        () => ({
            localStorage: {...localStorage},
            sessionStorage: {...sessionStorage}
        })
    """)

    print("LOCAL STORAGE")
    print(data["localStorage"])

    print("\\nSESSION STORAGE")
    print(data["sessionStorage"])

    browser.close()