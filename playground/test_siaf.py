from playwright.sync_api import sync_playwright

LOGIN_URL = "https://authorize.mef.gob.pe/auth/realms/mef/protocol/openid-connect/auth?response_type=code&scope=write%20read&client_id=jwtClient&redirect_uri=https://apps.mef.gob.pe/webmodulos/?data=eyJpZGFwbGljYXRpdm8iOjIwMDAxLCJpZHNpc3RlbWEiOiIyMDAwMCJ9"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    page.goto(LOGIN_URL)

    input("Inicia sesión. Cuando ya estés dentro del SIAF, presiona ENTER aquí...")

    context.storage_state(path="estado_siaf.json")
    browser.close()

print("Sesión guardada.")