import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("SIAF_TOKEN", "")

headers = {
    "Authorization": f"Bearer {TOKEN}"
}

r = requests.get(
    "https://apps.mef.gob.pe/v1/siaf-services/devengado/devengados",
    headers=headers,
    params={
        "anio": 2026,
        "expediente": 111,
        "page": 0,
        "page_size": 10,
        "sort": "-"
    }
)

print(r.status_code)
print(r.text[:1000])