import json
from playwright.sync_api import sync_playwright

import pandas as pd


BASE = "https://apps.mef.gob.pe/v1/siaf-services"
HOME = "https://apps.mef.gob.pe/websiaf/"


def fetch_json(page, url: str) -> dict:
    result = page.evaluate(
        """
        async (url) => {
            const token = localStorage.getItem("mefAuthToken");

            const r = await fetch(url, {
                method: "GET",
                headers: {
                    "Accept": "application/json",
                    "Authorization": `Bearer ${token}`
                }
            });

            return {
                status: r.status,
                text: await r.text()
            };
        }
        """,
        url,
    )

    if result["status"] != 200:
        raise Exception(f"Error {result['status']}: {result['text'][:500]}")

    return json.loads(result["text"])


def obtener_arbol(page, anio: int, expediente: int) -> dict:
    url = (
        f"{BASE}/devengado/devengados"
        f"?anio={anio}&expediente={expediente}&page=0&page_size=50&sort=-"
    )
    return fetch_json(page, url)


def obtener_compromiso(page, anio: int, expediente: int, secuencia: int) -> dict:
    url = f"{BASE}/compromisomensual/compromisos/{anio}/{expediente}/{secuencia}"
    data = fetch_json(page, url)
    d = data["detalle"]

    return {
        "anio": d.get("anio"),
        "expediente": d.get("expediente"),
        "secuencia": d.get("secuencia"),
        "fase": d.get("faseDescripcion"),
        "estado": d.get("estadoRegistroDescripcion"),
        "proveedor": d.get("proveedorNombre"),
        "ruc": d.get("proveedorNumeroDocumento"),
        "monto": d.get("monto"),
        "total_fase": d.get("totalFase"),
        "total_fase_siguiente": d.get("totalFaseSiguiente"),
        "modificaciones": d.get("totalModificaciones"),
        "saldo": d.get("saldo"),
        "saldo_aprobado": d.get("saldoAprobado"),
        "documento": d.get("codDocNombre"),
        "num_doc": d.get("numDoc"),
        "fecha_doc": d.get("fechaDoc"),
        "notas": d.get("notas"),
    }


def obtener_devengado(page, anio: int, expediente: int, secuencia: int) -> dict:
    url = f"{BASE}/devengado/devengados/{anio}/{expediente}/{secuencia}"
    data = fetch_json(page, url)
    d = data["detalle"]

    return {
        "anio": d.get("anio"),
        "expediente": d.get("expediente"),
        "secuencia": d.get("secuencia"),
        "fase": d.get("faseDescripcion"),
        "estado": d.get("estadoRegistroDescripcion"),
        "proveedor": d.get("proveedorNombre"),
        "ruc": d.get("proveedorNumeroDocumento"),
        "monto": d.get("monto"),
        "total_fase": d.get("totalFase"),
        "total_fase_siguiente": d.get("totalFaseSiguiente"),
        "modificaciones": d.get("totalModificaciones"),
        "saldo": d.get("saldo"),
        "saldo_aprobado": d.get("saldoAprobado"),
        "documento": d.get("codDocNombre"),
        "num_doc": d.get("numDoc"),
        "fecha_doc": d.get("fechaDoc"),
        "notas": d.get("notas"),
    }


def procesar_expediente(page, anio: int, expediente: int) -> list[dict]:
    arbol = obtener_arbol(page, anio, expediente)

    filas = []

    for bloque in arbol.get("content", []):
        for item in bloque.get("contenido", []):
            fase = item.get("fase")
            secuencia = item.get("secuencia")

            if fase == "C":
                fila = obtener_compromiso(page, anio, expediente, secuencia)
            elif fase == "D":
                fila = obtener_devengado(page, anio, expediente, secuencia)
            else:
                continue

            fila["anio"] = anio
            fila["expediente"] = expediente
            fila["secuencia"] = secuencia

            fila["nivel"] = item.get("nivel")
            fila["estado_arbol"] = item.get("estadoNombre")
            fila["secuencia_anterior"] = item.get("secuenciaAnterior")

            filas.append(fila)

    return filas


if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(storage_state="estado_siaf.json")
        page = context.new_page()

        page.goto(HOME)
        page.wait_for_timeout(5000)

        expedientes = [111, 85]

        todas_las_filas = []

        for expediente in expedientes:
            print(f"Procesando expediente {expediente}...")
            filas = procesar_expediente(page, 2026, expediente)
            todas_las_filas.extend(filas)

        df = pd.DataFrame(todas_las_filas)
        df.to_excel("resultado_siaf.xlsx", index=False)

        print("Excel generado: resultado_siaf.xlsx")
        print(df)

        browser.close()