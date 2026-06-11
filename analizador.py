from __future__ import annotations

import math
import unicodedata
from collections import Counter
from datetime import date, datetime

import pandas as pd


# ============================================================
# CONFIGURACIÓN
# ============================================================

INPUT_FILE = "resultado_siaf.xlsx"
OUTPUT_FILE = "analisis_siaf_definitivo.xlsx"

# Si quieres fijar una fecha manual:
# FECHA_CORTE = "2026-05-28"
FECHA_CORTE = None

TOLERANCIA_MONTO = 0.50
MAX_MESES_POSIBLES = 12

CATEGORIAS_VALIDAS = [
    "concluida",
    "rebaja_parcial",
    "rebaja_total",
    "por_rebajar",
    "vigente",
]


# ============================================================
# UTILIDADES
# ============================================================

def obtener_fecha_corte() -> date:
    if FECHA_CORTE:
        return datetime.strptime(FECHA_CORTE, "%Y-%m-%d").date()

    return date.today()


def normalizar_texto(texto) -> str:
    texto = str(texto or "").upper()
    texto = unicodedata.normalize("NFD", texto)
    texto = "".join(c for c in texto if unicodedata.category(c) != "Mn")
    return texto


def texto_fila(row) -> str:
    return normalizar_texto(
        f"{row.get('documento', '')} "
        f"{row.get('num_doc', '')} "
        f"{row.get('notas', '')}"
    )


def convertir_numero(valor) -> float:
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


def casi_igual(a, b, tolerancia=TOLERANCIA_MONTO) -> bool:
    return abs(float(a) - float(b)) <= tolerancia


def dividir_seguro(a, b):
    if b is None or b == 0:
        return None

    return a / b


def es_casi_entero(valor, tolerancia=0.05) -> bool:
    if valor is None:
        return False

    return abs(valor - round(valor)) <= tolerancia


def formato_entero(valor) -> str:
    if pd.isna(valor):
        return ""

    try:
        return str(int(float(valor)))
    except Exception:
        return str(valor)


def formato_secuencia(valor) -> str:
    if pd.isna(valor):
        return ""

    try:
        return str(int(float(valor))).zfill(4)
    except Exception:
        return str(valor)


def parsear_fecha(valor):
    fecha = pd.to_datetime(valor, errors="coerce")

    if pd.isna(fecha):
        return None

    return fecha.date()


def primer_dia_mes(fecha: date | None):
    if fecha is None:
        return None

    return date(fecha.year, fecha.month, 1)


def indice_mes(fecha: date) -> int:
    return fecha.year * 12 + fecha.month


def agregar_meses(fecha: date, meses: int) -> date:
    total = fecha.year * 12 + fecha.month - 1 + meses
    year = total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def nombre_mes(fecha: date | None) -> str:
    if fecha is None:
        return ""

    return fecha.strftime("%Y-%m")


# ============================================================
# DETECCIÓN TEXTUAL
# ============================================================

def detectar_retencion(row) -> bool:
    texto = texto_fila(row)

    patrones = [
        "RETENCION",
        "RETEN",
        "4TA",
        "CUARTA",
        "RENTA",
        "IMPUESTO A LA RENTA",
    ]

    return any(p in texto for p in patrones)


def detectar_primer_pago(row) -> bool:
    texto = texto_fila(row)

    patrones = [
        "PRIMER PAGO",
        "1ER PAGO",
        "1° PAGO",
        "1 PAGO",
        "PAGO 1",
    ]

    return any(p in texto for p in patrones)


def detectar_pago_parcial(row) -> bool:
    texto = texto_fila(row)

    patrones = [
        "PARCIAL",
        "PAGO PARCIAL",
        "SALDO",
        "LIQUIDACION",
        "LIQUIDACION FINAL",
        "SEGUNDO PAGO",
        "TERCER PAGO",
        "CUARTO PAGO",
        "QUINTO PAGO",
        "PAGO A CUENTA",
    ]

    return any(p in texto for p in patrones)


def detectar_posible_pago_acumulado(row) -> bool:
    texto = texto_fila(row)

    patrones = [
        "ENERO Y FEBRERO",
        "FEBRERO Y MARZO",
        "MARZO Y ABRIL",
        "ABRIL Y MAYO",
        "DOS MESES",
        "2 MESES",
        "PAGO ACUMULADO",
        "ACUMULADO",
    ]

    return any(p in texto for p in patrones)


# ============================================================
# AGRUPACIÓN DE DEVENGADOS
# ============================================================

def agrupar_devengados(devengados: pd.DataFrame) -> list[dict]:
    """
    Agrupa devengados normales con retenciones cercanas.

    Ejemplo:
    - Recibo: 7360
    - Retención 4ta: 640
    => grupo bruto: 8000
    """
    if devengados.empty:
        return []

    devengados = devengados.sort_values("secuencia").copy()

    grupos = []
    grupo_actual = None

    for _, row in devengados.iterrows():
        monto = convertir_numero(row.get("monto"))
        secuencia = formato_secuencia(row.get("secuencia"))
        fecha_doc = parsear_fecha(row.get("fecha_doc"))

        es_retencion = detectar_retencion(row)
        es_primer_pago = detectar_primer_pago(row)
        es_pago_parcial = detectar_pago_parcial(row)
        es_pago_acumulado = detectar_posible_pago_acumulado(row)

        nota = str(row.get("notas", ""))

        if not es_retencion:
            grupo_actual = {
                "secuencias": [secuencia],
                "fecha_doc_min": fecha_doc,
                "fecha_doc_max": fecha_doc,
                "monto_neto": monto,
                "retencion": 0.0,
                "monto_bruto": monto,
                "tiene_retencion": False,
                "tiene_primer_pago": es_primer_pago,
                "tiene_pago_parcial": es_pago_parcial,
                "tiene_pago_acumulado": es_pago_acumulado,
                "notas": [nota],
            }

            grupos.append(grupo_actual)

        else:
            if grupo_actual is None:
                grupo_actual = {
                    "secuencias": [secuencia],
                    "fecha_doc_min": fecha_doc,
                    "fecha_doc_max": fecha_doc,
                    "monto_neto": 0.0,
                    "retencion": monto,
                    "monto_bruto": monto,
                    "tiene_retencion": True,
                    "tiene_primer_pago": es_primer_pago,
                    "tiene_pago_parcial": es_pago_parcial,
                    "tiene_pago_acumulado": es_pago_acumulado,
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
                grupo_actual["tiene_pago_acumulado"] = (
                    grupo_actual["tiene_pago_acumulado"] or es_pago_acumulado
                )
                grupo_actual["notas"].append(nota)

                if fecha_doc:
                    fechas = [
                        f for f in [
                            grupo_actual["fecha_doc_min"],
                            grupo_actual["fecha_doc_max"],
                            fecha_doc,
                        ]
                        if f is not None
                    ]
                    grupo_actual["fecha_doc_min"] = min(fechas)
                    grupo_actual["fecha_doc_max"] = max(fechas)

    return grupos


# ============================================================
# INFERENCIA DE MONTO MENSUAL
# ============================================================

def construir_candidatos_monto_mensual(
    grupos: list[dict],
    monto_original: float,
    monto_final: float,
    modificaciones: float,
) -> list[dict]:
    candidatos = []

    montos = [
        round(float(g["monto_bruto"]), 2)
        for g in grupos
        if convertir_numero(g["monto_bruto"]) > 0
    ]

    if not montos:
        return candidatos

    conteos = Counter(montos)

    # 1) Montos repetidos en devengados.
    for monto, frecuencia in conteos.items():
        if frecuencia >= 2:
            candidatos.append({
                "monto": monto,
                "score": 100 + frecuencia,
                "metodo": "MONTO_MAS_REPETIDO_EN_DEVENGADOS",
                "confianza": "ALTA",
            })

    # 2) Monto que divide razonablemente el compromiso original.
    for monto in montos:
        if monto <= 0:
            continue

        meses = monto_original / monto if monto else None

        if meses and 1 <= meses <= MAX_MESES_POSIBLES and es_casi_entero(meses):
            candidatos.append({
                "monto": monto,
                "score": 92,
                "metodo": f"COMPROMISO_ORIGINAL_DIVISIBLE_EN_{round(meses)}_MESES",
                "confianza": "ALTA",
            })

    # 3) Monto que divide razonablemente el monto final luego de rebaja.
    if monto_final > 0:
        for monto in montos:
            meses = monto_final / monto if monto else None

            if meses and 1 <= meses <= MAX_MESES_POSIBLES and es_casi_entero(meses):
                candidatos.append({
                    "monto": monto,
                    "score": 86,
                    "metodo": f"MONTO_FINAL_DIVISIBLE_EN_{round(meses)}_MESES",
                    "confianza": "MEDIA_ALTA",
                })

    # 4) Primer pago detectado explícitamente.
    for grupo in grupos:
        if grupo["tiene_primer_pago"] and grupo["monto_bruto"] > 0:
            candidatos.append({
                "monto": round(float(grupo["monto_bruto"]), 2),
                "score": 82,
                "metodo": "PRIMER_PAGO_DETECTADO_EN_NOTAS",
                "confianza": "MEDIA_ALTA",
            })

    # 5) Primer devengado ante rebaja: suele representar mes completo.
    if modificaciones < 0 and montos:
        candidatos.append({
            "monto": round(float(montos[0]), 2),
            "score": 68,
            "metodo": "PRIMER_DEVENGADO_ANTE_REBAJA",
            "confianza": "MEDIA",
        })

    # 6) Monto máximo: evita tomar pagos parciales como mensualidad.
    monto_maximo = round(float(max(montos)), 2)

    candidatos.append({
        "monto": monto_maximo,
        "score": 60,
        "metodo": "MONTO_MAXIMO_SIN_REPETICION",
        "confianza": "MEDIA",
    })

    # Penalizar candidato si parece pago acumulado.
    for candidato in candidatos:
        for grupo in grupos:
            if casi_igual(candidato["monto"], grupo["monto_bruto"]) and grupo["tiene_pago_acumulado"]:
                candidato["score"] -= 15
                candidato["metodo"] += "_CON_ALERTA_PAGO_ACUMULADO"
                if candidato["confianza"] == "ALTA":
                    candidato["confianza"] = "MEDIA_ALTA"

    candidatos = sorted(
        candidatos,
        key=lambda x: (x["score"], x["monto"]),
        reverse=True,
    )

    return candidatos


def inferir_monto_mensual(
    grupos: list[dict],
    monto_original: float,
    monto_final: float,
    modificaciones: float,
) -> dict:
    if not grupos:
        return {
            "monto_mensual": None,
            "metodo": "SIN_DEVENGADOS",
            "confianza": "BAJA",
            "candidatos": "",
        }

    candidatos = construir_candidatos_monto_mensual(
        grupos=grupos,
        monto_original=monto_original,
        monto_final=monto_final,
        modificaciones=modificaciones,
    )

    if not candidatos:
        return {
            "monto_mensual": None,
            "metodo": "SIN_CANDIDATOS_VALIDOS",
            "confianza": "BAJA",
            "candidatos": "",
        }

    elegido = candidatos[0]

    candidatos_txt = " | ".join(
        f"{c['monto']}:{c['metodo']}:{c['confianza']}"
        for c in candidatos[:5]
    )

    return {
        "monto_mensual": elegido["monto"],
        "metodo": elegido["metodo"],
        "confianza": elegido["confianza"],
        "candidatos": candidatos_txt,
    }


# ============================================================
# INFERENCIA TEMPORAL
# ============================================================

def inferir_periodo_temporal(
    fecha_compromiso: date | None,
    monto_mensual: float | None,
    meses_previstos: float | None,
    fecha_corte: date,
) -> dict:
    if fecha_compromiso is None:
        return {
            "mes_inicio_estimado": "",
            "mes_fin_estimado": "",
            "meses_transcurridos_desde_inicio": None,
            "vigencia_temporal": "SIN_FECHA",
            "confianza_vigencia_temporal": "BAJA",
        }

    mes_inicio = primer_dia_mes(fecha_compromiso)
    mes_corte = primer_dia_mes(fecha_corte)

    meses_transcurridos = indice_mes(mes_corte) - indice_mes(mes_inicio)

    if monto_mensual and meses_previstos:
        meses_duracion = max(1, math.ceil(meses_previstos))
        mes_fin = agregar_meses(mes_inicio, meses_duracion - 1)

        if indice_mes(mes_fin) < indice_mes(mes_corte):
            vigencia = "VENCIDA_PROBABLE"
            confianza = "ALTA"
        elif indice_mes(mes_fin) == indice_mes(mes_corte):
            vigencia = "VIGENTE_O_POR_CERRAR"
            confianza = "MEDIA"
        else:
            vigencia = "VIGENTE_PROBABLE"
            confianza = "MEDIA_ALTA"

        return {
            "mes_inicio_estimado": nombre_mes(mes_inicio),
            "mes_fin_estimado": nombre_mes(mes_fin),
            "meses_transcurridos_desde_inicio": meses_transcurridos,
            "vigencia_temporal": vigencia,
            "confianza_vigencia_temporal": confianza,
        }

    # Sin monto mensual: heurística por antigüedad.
    if meses_transcurridos >= 2:
        vigencia = "VENCIDA_POR_ANTIGUEDAD"
        confianza = "MEDIA"
    elif meses_transcurridos in [0, 1]:
        vigencia = "VIGENTE_O_RECIENTE"
        confianza = "MEDIA_BAJA"
    else:
        vigencia = "FECHA_FUTURA_O_REVISAR"
        confianza = "BAJA"

    return {
        "mes_inicio_estimado": nombre_mes(mes_inicio),
        "mes_fin_estimado": "",
        "meses_transcurridos_desde_inicio": meses_transcurridos,
        "vigencia_temporal": vigencia,
        "confianza_vigencia_temporal": confianza,
    }


# ============================================================
# CLASIFICACIÓN PRINCIPAL
# ============================================================

def clasificar_categoria_expediente(
    monto_original: float,
    modificaciones: float,
    monto_final: float,
    saldo_compromiso: float,
    total_devengado: float,
    cantidad_devengados: int,
    vigencia_temporal: str,
) -> dict:
    """
    Tipología cerrada:
    - concluida
    - rebaja_parcial
    - rebaja_total
    - por_rebajar
    - vigente
    """

    tiene_devengados = cantidad_devengados > 0

    saldo_cero = casi_igual(saldo_compromiso, 0)
    devengado_cero = casi_igual(total_devengado, 0)
    modificaciones_cero = casi_igual(modificaciones, 0)
    saldo_integro = (
        casi_igual(saldo_compromiso, monto_original)
        or casi_igual(saldo_compromiso, monto_final)
    )

    rebaja_total = (
        modificaciones < 0
        and casi_igual(abs(modificaciones), monto_original)
        and casi_igual(monto_final, 0)
    )

    rebaja_parcial = (
        modificaciones < 0
        and abs(modificaciones) < monto_original - TOLERANCIA_MONTO
    )

    vencida_temporalmente = vigencia_temporal in [
        "VENCIDA_PROBABLE",
        "VENCIDA_POR_ANTIGUEDAD",
    ]

    # 1. Rebaja total
    if rebaja_total:
        if devengado_cero and saldo_cero:
            return {
                "categoria": "rebaja_total",
                "sub_estado": "rebaja_total_limpia",
                "confianza": "ALTA",
                "motivo": "La modificación negativa equivale al monto original; el monto final es cero; no hay saldo pendiente.",
                "accion_sugerida": "Registrar como orden totalmente rebajada.",
            }

        return {
            "categoria": "rebaja_total",
            "sub_estado": "rebaja_total_con_movimientos_para_revisar",
            "confianza": "MEDIA",
            "motivo": "La modificación equivale al monto original, pero existen devengados o saldos que deben revisarse.",
            "accion_sugerida": "Revisar manualmente porque hay señales mixtas.",
        }

    # 2. Rebaja parcial
    if rebaja_parcial:
        if casi_igual(total_devengado, monto_final) and saldo_cero:
            return {
                "categoria": "rebaja_parcial",
                "sub_estado": "rebaja_parcial_concluida",
                "confianza": "ALTA",
                "motivo": "Hubo rebaja parcial y el devengado cuadra con el monto final de la orden.",
                "accion_sugerida": "Registrar como orden ejecutada con rebaja parcial.",
            }

        if saldo_compromiso > TOLERANCIA_MONTO:
            return {
                "categoria": "rebaja_parcial",
                "sub_estado": "rebaja_parcial_con_saldo",
                "confianza": "MEDIA",
                "motivo": "Hubo rebaja parcial, pero aún queda saldo pendiente.",
                "accion_sugerida": "Revisar si el saldo pendiente debe devengarse o rebajarse.",
            }

        return {
            "categoria": "rebaja_parcial",
            "sub_estado": "rebaja_parcial_para_revisar",
            "confianza": "MEDIA",
            "motivo": "Existe modificación negativa parcial, pero el cuadre no es plenamente consistente.",
            "accion_sugerida": "Revisar devengados, saldo y modificación.",
        }

    # 3. Concluida
    if (
        modificaciones_cero
        and tiene_devengados
        and casi_igual(total_devengado, monto_original)
        and saldo_cero
    ):
        return {
            "categoria": "concluida",
            "sub_estado": "concluida_sin_rebaja",
            "confianza": "ALTA",
            "motivo": "El total devengado coincide con el monto original y el saldo es cero.",
            "accion_sugerida": "Registrar como concluida.",
        }

    if (
        tiene_devengados
        and casi_igual(total_devengado, monto_final)
        and saldo_cero
        and monto_final > 0
    ):
        return {
            "categoria": "concluida",
            "sub_estado": "concluida_por_cuadre_final",
            "confianza": "MEDIA_ALTA",
            "motivo": "El total devengado coincide con el monto final y el saldo es cero.",
            "accion_sugerida": "Registrar como concluida; revisar si hubo ampliaciones u otros ajustes.",
        }

    # 4. Por rebajar: sin pago, sin rebaja, saldo íntegro, y vencida o antigua.
    if (
        not tiene_devengados
        and modificaciones_cero
        and saldo_integro
        and vencida_temporalmente
    ):
        return {
            "categoria": "por_rebajar",
            "sub_estado": "sin_devengados_sin_rebaja_y_vencida",
            "confianza": "ALTA",
            "motivo": "No registra devengados ni rebajas; conserva saldo íntegro y por fecha parece vencida.",
            "accion_sugerida": "Priorizar revisión para rebaja/anulación.",
        }

    # 5. Por rebajar: pago parcial sin rebaja y temporalmente vencida.
    if (
        tiene_devengados
        and modificaciones_cero
        and saldo_compromiso > TOLERANCIA_MONTO
        and vencida_temporalmente
    ):
        return {
            "categoria": "por_rebajar",
            "sub_estado": "devengado_parcial_sin_rebaja_y_vencida",
            "confianza": "MEDIA_ALTA",
            "motivo": "Registra devengado parcial, conserva saldo pendiente, no tiene rebaja y por fecha parece vencida.",
            "accion_sugerida": "Revisar saldo pendiente; probablemente falta rebajar.",
        }

    # 6. Vigente: saldo pendiente, sin evidencia fuerte de vencimiento.
    if saldo_compromiso > TOLERANCIA_MONTO:
        return {
            "categoria": "vigente",
            "sub_estado": "saldo_pendiente_con_posible_vigencia",
            "confianza": "MEDIA",
            "motivo": "Tiene saldo pendiente, pero la fecha no permite afirmar con alta confianza que deba rebajarse.",
            "accion_sugerida": "Revisar con cuidado si corresponde devengar o esperar cierre.",
        }

    # 7. Vigente o revisar: sin devengado, reciente.
    if (
        not tiene_devengados
        and modificaciones_cero
        and saldo_integro
    ):
        return {
            "categoria": "vigente",
            "sub_estado": "sin_devengado_reciente_o_en_ejecucion",
            "confianza": "MEDIA_BAJA",
            "motivo": "No tiene devengados ni rebajas, pero por fecha todavía podría estar vigente.",
            "accion_sugerida": "Monitorear; si supera el periodo probable, pasará a por_rebajar.",
        }

    # 8. Fallback: elegir vigente con baja confianza, no inventar cierre.
    return {
        "categoria": "vigente",
        "sub_estado": "caso_no_concluyente",
        "confianza": "BAJA",
        "motivo": "No cumple reglas fuertes de conclusión, rebaja o por_rebajar.",
        "accion_sugerida": "Revisar manualmente.",
    }


# ============================================================
# ANÁLISIS POR EXPEDIENTE
# ============================================================

def analizar_expediente(expediente, data: pd.DataFrame, fecha_corte: date):
    data = data.copy()

    data["fase"] = (
        data["fase"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    compromisos = data[
        data["fase"].str.contains("COMPROMISO", na=False)
    ].sort_values("secuencia")

    devengados = data[
        data["fase"].str.contains("DEVENGADO", na=False)
    ].sort_values("secuencia")

    if compromisos.empty:
        return {
            "expediente": expediente,
            "categoria_expediente": "",
            "error": "SIN_COMPROMISO",
        }, []

    compromiso = compromisos.iloc[0]

    grupos = agrupar_devengados(devengados)

    monto_original = convertir_numero(compromiso.get("monto"))
    modificaciones = convertir_numero(compromiso.get("modificaciones"))
    monto_final = monto_original + modificaciones
    saldo_compromiso = convertir_numero(compromiso.get("saldo"))

    total_devengado_raw = convertir_numero(devengados["monto"].sum())
    total_devengado_agrupado = sum(g["monto_bruto"] for g in grupos)

    fecha_compromiso = parsear_fecha(compromiso.get("fecha_doc"))

    resultado_mensual = inferir_monto_mensual(
        grupos=grupos,
        monto_original=monto_original,
        monto_final=monto_final,
        modificaciones=modificaciones,
    )

    monto_mensual = resultado_mensual["monto_mensual"]

    meses_previstos = dividir_seguro(monto_original, monto_mensual)
    meses_finales = dividir_seguro(monto_final, monto_mensual)
    meses_devengados = dividir_seguro(total_devengado_agrupado, monto_mensual)

    if modificaciones < 0:
        meses_rebajados = dividir_seguro(abs(modificaciones), monto_mensual)
    else:
        meses_rebajados = 0

    if meses_previstos is not None:
        meses_pendientes = meses_previstos - (meses_devengados or 0) - (meses_rebajados or 0)
        meses_pendientes = max(0, meses_pendientes)
    else:
        meses_pendientes = None

    periodo = inferir_periodo_temporal(
        fecha_compromiso=fecha_compromiso,
        monto_mensual=monto_mensual,
        meses_previstos=meses_previstos,
        fecha_corte=fecha_corte,
    )

    clasificacion = clasificar_categoria_expediente(
        monto_original=monto_original,
        modificaciones=modificaciones,
        monto_final=monto_final,
        saldo_compromiso=saldo_compromiso,
        total_devengado=total_devengado_agrupado,
        cantidad_devengados=len(devengados),
        vigencia_temporal=periodo["vigencia_temporal"],
    )

    diferencia_final_vs_devengado = monto_final - total_devengado_agrupado

    if casi_igual(diferencia_final_vs_devengado, 0):
        estado_cuadre = "CUADRA"
    elif diferencia_final_vs_devengado > 0:
        estado_cuadre = "SALDO_NO_DEVENGADO"
    else:
        estado_cuadre = "DEVENGADO_SUPERA_MONTO_FINAL"

    resumen = {
        "fecha_corte": fecha_corte.isoformat(),

        "expediente": int(expediente),
        "proveedor": compromiso.get("proveedor"),
        "ruc": formato_entero(compromiso.get("ruc")),

        "categoria_expediente": clasificacion["categoria"],
        "sub_estado": clasificacion["sub_estado"],
        "confianza_categoria": clasificacion["confianza"],
        "motivo_categoria": clasificacion["motivo"],
        "accion_sugerida": clasificacion["accion_sugerida"],

        "monto_original": redondear(monto_original),
        "modificaciones": redondear(modificaciones),
        "monto_final": redondear(monto_final),
        "saldo_compromiso": redondear(saldo_compromiso),

        "total_devengado_raw": redondear(total_devengado_raw),
        "total_devengado_agrupado": redondear(total_devengado_agrupado),
        "diferencia_final_vs_devengado": redondear(diferencia_final_vs_devengado),
        "estado_cuadre": estado_cuadre,

        "monto_mensual_inferido": redondear(monto_mensual),
        "metodo_monto_mensual": resultado_mensual["metodo"],
        "confianza_monto_mensual": resultado_mensual["confianza"],
        "candidatos_monto_mensual": resultado_mensual["candidatos"],

        "meses_previstos": redondear(meses_previstos),
        "meses_finales": redondear(meses_finales),
        "meses_devengados": redondear(meses_devengados),
        "meses_rebajados": redondear(meses_rebajados),
        "meses_pendientes": redondear(meses_pendientes),

        "meses_previstos_casi_enteros": es_casi_entero(meses_previstos),
        "meses_finales_casi_enteros": es_casi_entero(meses_finales),
        "meses_pendientes_casi_enteros": es_casi_entero(meses_pendientes),

        "fecha_doc_compromiso": compromiso.get("fecha_doc"),
        "mes_inicio_estimado": periodo["mes_inicio_estimado"],
        "mes_fin_estimado": periodo["mes_fin_estimado"],
        "meses_transcurridos_desde_inicio": periodo["meses_transcurridos_desde_inicio"],
        "vigencia_temporal": periodo["vigencia_temporal"],
        "confianza_vigencia_temporal": periodo["confianza_vigencia_temporal"],

        "cantidad_devengados": len(devengados),
        "cantidad_grupos_devengado": len(grupos),
        "tiene_retenciones": any(g["tiene_retencion"] for g in grupos),
        "tiene_pago_parcial": any(g["tiene_pago_parcial"] for g in grupos),
        "tiene_pago_acumulado": any(g["tiene_pago_acumulado"] for g in grupos),

        "documento_compromiso": compromiso.get("documento"),
        "num_doc_compromiso": compromiso.get("num_doc"),
        "notas_compromiso": compromiso.get("notas"),
    }

    grupos_detalle = []

    for idx, grupo in enumerate(grupos, start=1):
        grupos_detalle.append({
            "expediente": int(expediente),
            "grupo_devengado": idx,
            "secuencias": ", ".join(grupo["secuencias"]),
            "fecha_doc_min": grupo["fecha_doc_min"],
            "fecha_doc_max": grupo["fecha_doc_max"],
            "monto_neto": redondear(grupo["monto_neto"]),
            "retencion": redondear(grupo["retencion"]),
            "monto_bruto": redondear(grupo["monto_bruto"]),
            "tiene_retencion": grupo["tiene_retencion"],
            "tiene_primer_pago": grupo["tiene_primer_pago"],
            "tiene_pago_parcial": grupo["tiene_pago_parcial"],
            "tiene_pago_acumulado": grupo["tiene_pago_acumulado"],
            "notas": " | ".join(grupo["notas"]),
        })

    return resumen, grupos_detalle


# ============================================================
# PREPARACIÓN
# ============================================================

def preparar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    columnas_requeridas = [
        "expediente",
        "fase",
        "monto",
        "modificaciones",
        "saldo",
    ]

    faltantes = [c for c in columnas_requeridas if c not in df.columns]

    if faltantes:
        raise ValueError(f"Faltan columnas requeridas: {faltantes}")

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


def ordenar_columnas_resumen(df: pd.DataFrame) -> pd.DataFrame:
    columnas_prioritarias = [
        "fecha_corte",
        "expediente",
        "proveedor",
        "ruc",

        "categoria_expediente",
        "sub_estado",
        "confianza_categoria",
        "motivo_categoria",
        "accion_sugerida",

        "monto_original",
        "modificaciones",
        "monto_final",
        "saldo_compromiso",
        "total_devengado_agrupado",
        "diferencia_final_vs_devengado",
        "estado_cuadre",

        "monto_mensual_inferido",
        "metodo_monto_mensual",
        "confianza_monto_mensual",

        "meses_previstos",
        "meses_finales",
        "meses_devengados",
        "meses_rebajados",
        "meses_pendientes",

        "fecha_doc_compromiso",
        "mes_inicio_estimado",
        "mes_fin_estimado",
        "vigencia_temporal",
        "confianza_vigencia_temporal",

        "cantidad_devengados",
        "cantidad_grupos_devengado",
        "tiene_retenciones",
        "tiene_pago_parcial",
        "tiene_pago_acumulado",
    ]

    existentes = [c for c in columnas_prioritarias if c in df.columns]
    restantes = [c for c in df.columns if c not in existentes]

    return df[existentes + restantes]


# ============================================================
# MAIN
# ============================================================

def main():
    fecha_corte = obtener_fecha_corte()

    df = pd.read_excel(INPUT_FILE)
    df = preparar_dataframe(df)

    resumenes = []
    grupos_todos = []

    for expediente, data in df.groupby("expediente"):
        try:
            resumen, grupos = analizar_expediente(
                expediente=expediente,
                data=data,
                fecha_corte=fecha_corte,
            )

            resumenes.append(resumen)
            grupos_todos.extend(grupos)

        except Exception as e:
            resumenes.append({
                "fecha_corte": fecha_corte.isoformat(),
                "expediente": expediente,
                "categoria_expediente": "",
                "error": str(e),
            })

    resumen_df = pd.DataFrame(resumenes)
    grupos_df = pd.DataFrame(grupos_todos)

    resumen_df = ordenar_columnas_resumen(resumen_df)

    conteo_categorias = (
        resumen_df["categoria_expediente"]
        .value_counts(dropna=False)
        .reset_index()
    )

    conteo_categorias.columns = [
        "categoria_expediente",
        "cantidad",
    ]

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

        conteo_categorias.to_excel(
            writer,
            sheet_name="conteo_categorias",
            index=False,
        )

    print(f"Excel generado: {OUTPUT_FILE}")
    print()
    print("Conteo por categoría:")
    print(conteo_categorias)
    print()
    print("Vista previa:")
    print(
        resumen_df[
            [
                "expediente",
                "categoria_expediente",
                "confianza_categoria",
                "monto_mensual_inferido",
                "meses_previstos",
                "meses_devengados",
                "meses_rebajados",
                "meses_pendientes",
                "vigencia_temporal",
            ]
        ].head(20)
    )


if __name__ == "__main__":
    main()