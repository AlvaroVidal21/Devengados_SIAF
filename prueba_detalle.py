from playwright.sync_api import sync_playwright

API = "https://apps.mef.gob.pe/v1/siaf-services/compromisomensual/compromisos/2026/111/1"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(storage_state="estado_siaf.json")
    page = context.new_page()

    page.goto("https://apps.mef.gob.pe/websiaf/")
    page.wait_for_timeout(5000)

    result = page.evaluate(f"""
        async () => {{
            const token = localStorage.getItem("mefAuthToken");

            const r = await fetch("{API}", {{
                method: "GET",
                headers: {{
                    "Accept": "application/json",
                    "Authorization": `Bearer ${{token}}`
                }}
            }});

            return {{
                status: r.status,
                text: await r.text()
            }};
        }}
    """)

    print(result["status"])
    print(result["text"][:3000])

    browser.close()