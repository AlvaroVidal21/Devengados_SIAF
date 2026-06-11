import unicodedata
from collections import Counter

import pandas as pd


INPUT_FILE = "resultado_siaf.xlsx"
OUTPUT_FILE = "analisis_siaf.xlsx"

TOLERANCIA_MONTO = 0.50
MAX_MESES_POSIBLES = 12


# =========================
# UTILIDADES GENERALES
# =========================

def normalizar_texto(texto):
    texto = str(texto or "").upper()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def texto_fila(row):
    return normalizar_texto(
        f"{row.get('documento', '')} "
        f"{row.get('num_doc', '')} "
        f"{row.get('notas', '')}"
    )


def convertir_numero(valor):
    if pd.isna(valor):
        return 0.0

    try:
        return float(valor)
    except Exception:
        return 0.0


def redondear(valor, decimales=2):
    if valor is None:
        return None

    try:
        return round(float(valor), decimales)
    except Exception:
        return None


def casi_igual(a, b, tolerancia=TOLERANCIA_MONTO):
    return abs(float(a) - float(b)) <= tolerancia


def dividir_seguro(a, b):
    if b is None or b == 0:
        return None

    return a / b


def es_casi_entero(valor):
    if valor is None:
        return False

    return abs(valor - round(valor)) <= 0.05


def formato_entero(valor):
    if pd.isna(valor):
        return ""

    try:
        return str(int(float(valor)))
    except Exception:
        return str(valor)


def formato_secuencia(valor):
    if pd.isna(valor):
        return ""

    try:
        return str(int(float(valor))).zfill(4)
    except Exception:
        return str(valor)


# =========================
# DETECCIÓN DE TEXTOS
# =========================

def detectar_retencion(row):
    texto = texto_fila(row)

    patrones = [
        "RETENCION",
        "RETEN",
        "4TA",
        "CUARTA",
        "RENTA",
    ]

    return any(p in texto for p in patrones)


def detectar_primer_pago(row):
    texto = texto_fila(row)

    patrones = [
        "PRIMER PAGO",
        "1ER PAGO",
        "1° PAGO",
        "PAGO 1",
    ]

    return any(p in texto for p in patrones)


def detectar_pago_parcial(row):
    texto = texto_fila(row)

    patrones = [
        "PAGO PARCIAL",
        "PARCIAL",
        "SALDO",
        "LIQUIDACION",
        "LIQUIDACION FINAL",
        "SEGUNDO PAGO",
        "TERCER PAGO",
        "CUARTO PAGO",
    ]

    return any(p in texto for p in patrones)


# =========================
# AGRUPACIÓN DE DEVENGADOS
# =========================

def agrupar_devengados(devengados):
    devengados = devengados.sort_values("secuencia").copy()

    grupos = []
    grupo_actual = None

    for _, row in devengados.iterrows():
        monto = convertir_numero(row.get("monto"))
        secuencia = formato_secuencia(row.get("secuencia"))

        es_retencion = detectar_retencion(row)
        es_primer_pago = detectar_primer_pago(row)
        es_pago_parcial = detectar_pago_parcial(row)

        nota = str(row.get("notas", ""))

        if not es_retencion:
            grupo_actual = {
                "secuencias": [secuencia],
                "monto_neto": monto,
                "retencion": 0.0,
                "monto_bruto": monto,
                "tiene_retencion": False,
                "tiene_primer_pago": es_primer_pago,
                "tiene_pago_parcial": es_pago_parcial,
                "notas": [nota],
            }

            grupos.append(grupo_actual)

        else:
            if grupo_actual is None:
                grupo_actual = {
                    "secuencias": [secuencia],
                    "monto_neto": 0.0,
                    "retencion": monto,
                    "monto_bruto": monto,
                    "tiene_retencion": True,
                    "tiene_primer_pago": es_primer_pago,
                    "tiene_pago_parcial": es_pago_parcial,
                    "notas": [nota],
                }

                grupos.append(grupo_actual)

            else:
                grupo_actual["secuencias"].append(secuencia)
                grupo_actual["retencion"] += monto
                grupo_actual["monto_bruto"] += monto
                grupo_actual["tiene_retencion"] = True
                grupo_actual["tiene_primer_pago"] = (
                    grupo_actual["tiene_primer_pago"] or es_primer_pago
                )
                grupo_actual["tiene_pago_parcial"] = (
                    grupo_actual["tiene_pago_parcial"] or es_pago_parcial
                )
                grupo_actual["notas"].append(nota)

    return grupos


# =========================
# INFERENCIA DE MONTO MENSUAL
# =========================

def buscar_monto_por_division_compromiso(monto_original, montos):
    if monto_original <= 0 or not montos:
        return None

    for meses in range(1, MAX_MESES_POSIBLES + 1):
        candidato = monto_original / meses

        for monto in montos:
            if abs(candidato - monto) <= TOLERANCIA_MONTO:
                return {
                    "monto_mensual": round(float(monto), 2),
                    "metodo": f"COMPROMISO DIVISIBLE ENTRE {meses} MESES",
                    "confianza": "ALTA",
                }

    return None


def elegir_monto_mensual(grupos, monto_original, modificaciones):
    if not grupos:
        return {
            "monto_mensual": None,
            "metodo": "SIN DEVENGADOS",
            "confianza": "BAJA",
        }

    montos = [
        round(float(g["monto_bruto"]), 2)
        for g in grupos
        if convertir_numero(g["monto_bruto"]) > 0
    ]

    if not montos:
        return {
            "monto_mensual": None,
            "metodo": "SIN MONTOS VALIDOS",
            "confianza": "BAJA",
        }

    conteos = Counter(montos)
    monto_mas_repetido, frecuencia = conteos.most_common(1)[0]

    if frecuencia >= 2:
        return {
            "monto_mensual": monto_mas_repetido,
            "metodo": "MONTO MAS REPETIDO EN DEVENGADOS",
            "confianza": "ALTA",
        }

    resultado_division = buscar_monto_por_division_compromiso(
        monto_original,
        montos,
    )

    if resultado_division is not None:
        return resultado_division

    for grupo in grupos:
        if grupo["tiene_primer_pago"] and grupo["monto_bruto"] > 0:
            return {
                "monto_mensual": round(float(grupo["monto_bruto"]), 2),
                "metodo": "PRIMER PAGO DETECTADO EN NOTAS",
                "confianza": "MEDIA_ALTA",
            }

    primer_monto = float(montos[0])
    monto_maximo = float(max(montos))

    if modificaciones < 0 and primer_monto >= monto_maximo:
        return {
            "monto_mensual": round(primer_monto, 2),
            "metodo": "PRIMER DEVENGADO ANTE REBAJA",
            "confianza": "MEDIA",
        }

    return {
        "monto_mensual": round(monto_maximo, 2),
        "metodo": "MONTO MAXIMO SIN REPETICION",
        "confianza": "MEDIA",
    }


# =========================
# CLASIFICACIÓN OPERATIVA
# =========================

def clasificar_estado_operativo(
    monto_original,
    modificaciones,
    monto_final_estimado,
    total_devengado,
    saldo_compromiso,
    cantidad_devengados,
):
    tiene_devengados = cantidad_devengados > 0

    rebaja_total = (
        modificaciones < 0
        and casi_igual(abs(modificaciones), monto_original)
        and casi_igual(monto_final_estimado, 0)
    )

    saldo_integro = (
        casi_igual(saldo_compromiso, monto_original)
        or casi_igual(saldo_compromiso, monto_final_estimado)
    )

    if not tiene_devengados:
        if rebaja_total:
            return {
                "estado_operativo": "REBAJA_TOTAL",
                "accion_sugerida": "Orden rebajada totalmente; no registra devengados.",
            }

        if casi_igual(modificaciones, 0) and saldo_integro:
            return {
                "estado_operativo": "POR_REBAJAR",
                "accion_sugerida": "No registra devengados y conserva saldo íntegro; revisar rebaja/anulación.",
            }

        if modificaciones < 0 and monto_final_estimado > 0:
            return {
                "estado_operativo": "REBAJA_PARCIAL_SIN_DEVENGADO",
                "accion_sugerida": "Tiene rebaja parcial, pero aún queda saldo sin devengar.",
            }

        return {
            "estado_operativo": "COMPROMISO_SIN_DEVENGADO",
            "accion_sugerida": "Compromiso sin devengados; revisar ejecución o rebaja.",
        }

    if rebaja_total:
        return {
            "estado_operativo": "REBAJA_TOTAL_CON_MOVIMIENTO",
            "accion_sugerida": "Revisar: figura rebaja total, pero existen devengados.",
        }

    if casi_igual(total_devengado, monto_final_estimado) and casi_igual(saldo_compromiso, 0):
        if modificaciones < 0:
            return {
                "estado_operativo": "EJECUTADO_CON_REBAJA",
                "accion_sugerida": "Devengado cuadra con monto final luego de rebaja.",
            }

        return {
            "estado_operativo": "EJECUTADO_COMPLETO",
            "accion_sugerida": "Devengado completo sin rebaja.",
        }

    if saldo_compromiso > TOLERANCIA_MONTO:
        if modificaciones < 0:
            return {
                "estado_operativo": "DEVENGADO_PARCIAL_CON_REBAJA_Y_SALDO",
                "accion_sugerida": "Hay devengado parcial, rebaja y saldo pendiente; revisar si falta devengar o rebajar.",
            }

        return {
            "estado_operativo": "DEVENGADO_PARCIAL_CON_SALDO",
            "accion_sugerida": "Hay devengado parcial y saldo pendiente; revisar ejecución o rebaja.",
        }

    if total_devengado < monto_final_estimado:
        return {
            "estado_operativo": "FALTA_DEVENGAR",
            "accion_sugerida": "El monto devengado es menor al monto final estimado.",
        }

    if total_devengado > monto_final_estimado:
        return {
            "estado_operativo": "REVISAR_EXCESO_O_REDONDEO",
            "accion_sugerida": "El devengado supera el monto final estimado; revisar redondeo, retenciones o datos.",
        }

    return {
        "estado_operativo": "REVISAR",
        "accion_sugerida": "Caso no clasificado automáticamente.",
    }


# =========================
# ANÁLISIS POR EXPEDIENTE
# =========================

def analizar_expediente(expediente, data):
    data = data.copy()
    data["fase"] = data["fase"].astype(str).str.upper().str.strip()

    compromisos = data[data["fase"] == "COMPROMISO"].sort_values("secuencia")
    devengados = data[data["fase"] == "DEVENGADO"].sort_values("secuencia")

    if compromisos.empty:
        return {
            "expediente": expediente,
            "error": "SIN COMPROMISO",
        }, []

    compromiso = compromisos.iloc[0]

    grupos = agrupar_devengados(devengados)

    monto_original = convertir_numero(compromiso.get("monto"))
    modificaciones = convertir_numero(compromiso.get("modificaciones"))
    monto_final_estimado = monto_original + modificaciones
    saldo_compromiso = convertir_numero(compromiso.get("saldo"))

    total_devengado_raw = convertir_numero(devengados["monto"].sum())
    total_devengado_agrupado = sum(g["monto_bruto"] for g in grupos)

    resultado_mensual = elegir_monto_mensual(
        grupos=grupos,
        monto_original=monto_original,
        modificaciones=modificaciones,
    )

    monto_mensual = resultado_mensual["monto_mensual"]

    meses_previstos = dividir_seguro(monto_original, monto_mensual)
    meses_finales = dividir_seguro(monto_final_estimado, monto_mensual)
    meses_devengados = dividir_seguro(total_devengado_agrupado, monto_mensual)

    if modificaciones < 0:
        meses_rebajados = dividir_seguro(abs(modificaciones), monto_mensual)
    else:
        meses_rebajados = 0

    diferencia_final_vs_devengado = monto_final_estimado - total_devengado_agrupado

    if abs(diferencia_final_vs_devengado) <= TOLERANCIA_MONTO:
        estado_cuadre = "CUADRA"
    elif diferencia_final_vs_devengado > 0:
        estado_cuadre = "FALTA_DEVENGAR"
    else:
        estado_cuadre = "REVISAR_EXCESO_O_REDONDEO"

    clasificacion_operativa = clasificar_estado_operativo(
        monto_original=monto_original,
        modificaciones=modificaciones,
        monto_final_estimado=monto_final_estimado,
        total_devengado=total_devengado_agrupado,
        saldo_compromiso=saldo_compromiso,
        cantidad_devengados=len(devengados),
    )

    resumen = {
        "expediente": int(expediente),
        "proveedor": compromiso.get("proveedor"),
        "ruc": formato_entero(compromiso.get("ruc")),

        "monto_original": redondear(monto_original),
        "modificaciones": redondear(modificaciones),
        "monto_final_estimado": redondear(monto_final_estimado),
        "saldo_compromiso": redondear(saldo_compromiso),

        "total_devengado_raw": redondear(total_devengado_raw),
        "total_devengado_agrupado": redondear(total_devengado_agrupado),
        "diferencia_final_vs_devengado": redondear(diferencia_final_vs_devengado),

        "monto_mensual_inferido": redondear(monto_mensual),
        "metodo_monto_mensual": resultado_mensual["metodo"],
        "confianza_monto_mensual": resultado_mensual["confianza"],

        "meses_previstos": redondear(meses_previstos),
        "meses_finales_estimados": redondear(meses_finales),
        "meses_devengados_estimados": redondear(meses_devengados),
        "meses_rebajados_estimados": redondear(meses_rebajados),

        "meses_previstos_casi_enteros": es_casi_entero(meses_previstos),
        "meses_finales_casi_enteros": es_casi_entero(meses_finales),

        "cantidad_devengados": len(devengados),
        "cantidad_grupos_devengado": len(grupos),
        "tiene_retenciones": any(g["tiene_retencion"] for g in grupos),

        "estado_rebaja": "REBAJADO" if modificaciones < 0 else "SIN_REBAJA",
        "estado_cuadre": estado_cuadre,

        "estado_operativo": clasificacion_operativa["estado_operativo"],
        "accion_sugerida": clasificacion_operativa["accion_sugerida"],

        "documento_compromiso": compromiso.get("documento"),
        "num_doc_compromiso": compromiso.get("num_doc"),
        "fecha_doc_compromiso": compromiso.get("fecha_doc"),
        "notas_compromiso": compromiso.get("notas"),
    }

    grupos_detalle = []

    for idx, grupo in enumerate(grupos, start=1):
        grupos_detalle.append({
            "expediente": int(expediente),
            "grupo_devengado": idx,
            "secuencias": ", ".join(grupo["secuencias"]),
            "monto_neto": redondear(grupo["monto_neto"]),
            "retencion": redondear(grupo["retencion"]),
            "monto_bruto": redondear(grupo["monto_bruto"]),
            "tiene_retencion": grupo["tiene_retencion"],
            "tiene_primer_pago": grupo["tiene_primer_pago"],
            "tiene_pago_parcial": grupo["tiene_pago_parcial"],
            "notas": " | ".join(grupo["notas"]),
        })

    return resumen, grupos_detalle


# =========================
# PREPARACIÓN DEL DATAFRAME
# =========================

def preparar_dataframe(df):
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    columnas_numericas = [
        "anio",
        "expediente",
        "secuencia",
        "monto",
        "total_fase",
        "total_fase_siguiente",
        "modificaciones",
        "saldo",
        "saldo_aprobado",
        "nivel",
        "secuencia_anterior",
    ]

    for col in columnas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


# =========================
# MAIN
# =========================

def main():
    df = pd.read_excel(INPUT_FILE)
    df = preparar_dataframe(df)

    resumenes = []
    grupos_todos = []

    for expediente, data in df.groupby("expediente"):
        try:
            resumen, grupos = analizar_expediente(expediente, data)
            resumenes.append(resumen)
            grupos_todos.extend(grupos)

        except Exception as e:
            resumenes.append({
                "expediente": expediente,
                "error": str(e),
            })

    resumen_df = pd.DataFrame(resumenes)
    grupos_df = pd.DataFrame(grupos_todos)

    with pd.ExcelWriter(OUTPUT_FILE, engine="openpyxl") as writer:
        resumen_df.to_excel(
            writer,
            sheet_name="resumen_expedientes",
            index=False,
        )

        grupos_df.to_excel(
            writer,
            sheet_name="grupos_devengado",
            index=False,
        )

    print(f"Excel generado: {OUTPUT_FILE}")
    print(resumen_df)


if __name__ == "__main__":
    main()