import os
import time
import requests
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

BASE = "https://apps.mef.gob.pe/v1/siaf-services"

TOKEN = os.getenv("SIAF_TOKEN", "")

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

def get_json(url, params=None):
    response = requests.get(
        url,
        headers=headers,
        params=params,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def consultar_arbol(anio, expediente):
    url = f"{BASE}/devengado/devengados"
    params = {
        "anio": anio,
        "expediente": expediente,
        "page": 0,
        "page_size": 50,
        "sort": "-"
    }
    return get_json(url, params)


def consultar_solicitud(anio, expediente):
    url = f"{BASE}/rendicion/solicitudes/{anio}/{expediente}"
    return get_json(url)


def consultar_detalle(anio, expediente, fase, secuencia):
    if fase == "C":
        url = f"{BASE}/compromisomensual/compromisos/{anio}/{expediente}/{secuencia}"
    elif fase == "D":
        url = f"{BASE}/devengado/devengados/{anio}/{expediente}/{secuencia}"
    else:
        return None

    return get_json(url)


def extraer_resumen(detalle_json):
    d = detalle_json.get("detalle", {})

    return {
        "anio": d.get("anio"),
        "entidad": d.get("entidad"),
        "expediente": d.get("expediente"),
        "secuencia": str(d.get("secuencia")).zfill(4) if d.get("secuencia") is not None else None,
        "fase": d.get("fase"),
        "fase_descripcion": d.get("faseDescripcion"),
        "estado": d.get("estadoRegistroDescripcion"),
        "proveedor_documento": d.get("proveedorNumeroDocumento"),
        "proveedor_nombre": d.get("proveedorNombre"),
        "monto": d.get("monto"),
        "total_fase": d.get("totalFase"),
        "total_fase_siguiente": d.get("totalFaseSiguiente"),
        "total_modificaciones": d.get("totalModificaciones"),
        "saldo": d.get("saldo"),
        "saldo_aprobado": d.get("saldoAprobado"),
        "cod_doc": d.get("codDoc"),
        "documento": d.get("codDocNombre"),
        "num_doc": d.get("numDoc"),
        "fecha_doc": d.get("fechaDoc"),
        "certificado": d.get("certificado"),
        "certificado_secuencia": d.get("certificadoSecuencia"),
        "clasificador_1": (
            d.get("clasificadores", [{}])[0].get("clasificador")
            if d.get("clasificadores") else None
        ),
        "clasificador_desc_1": (
            d.get("clasificadores", [{}])[0].get("clasificadorDescripcion")
            if d.get("clasificadores") else None
        ),
        "notas": d.get("notas"),
    }


def procesar_expediente(anio, expediente):
    filas = []

    arbol = consultar_arbol(anio, expediente)

    for bloque in arbol.get("content", []):
        for item in bloque.get("contenido", []):
            fase = item.get("fase")
            secuencia = item.get("secuencia")

            detalle = consultar_detalle(anio, expediente, fase, secuencia)

            if detalle is None:
                continue

            fila = extraer_resumen(detalle)

            fila["fase_arbol"] = item.get("faseNombre")
            fila["estado_arbol"] = item.get("estadoNombre")
            fila["nivel"] = item.get("nivel")
            fila["secuencia_anterior"] = item.get("secuenciaAnterior")

            filas.append(fila)

            time.sleep(0.5)

    return filas


anio = 2026
expedientes = [111]

todas_las_filas = []

for expediente in expedientes:
    try:
        filas = procesar_expediente(anio, expediente)
        todas_las_filas.extend(filas)
    except requests.HTTPError as e:
        todas_las_filas.append({
            "anio": anio,
            "expediente": expediente,
            "error": str(e)
        })

df = pd.DataFrame(todas_las_filas)
df.to_excel("resultado_siaf.xlsx", index=False)

print(df)