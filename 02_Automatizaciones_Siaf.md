# Devengados SIAF — Extracción, Conciliación y Clasificación de Órdenes de Servicio

Sistema inteligente que automatiza la extracción de registros financieros desde la API protegida del SIAF (MEF - Perú) y, mediante algoritmos heurísticos de scoring, deduce el estado operativo y presupuestal de cada orden de servicio.

---

## Stack Tecnológico

| Tecnología | Rol |
|---|---|
| **Python 3.12** | Core del sistema |
| **Playwright** | Motor de extracción con persistencia de sesión |
| **Pandas** | Procesamiento de datos y motor de scoring |
| **OpenPyXL** | Generación de reportes Excel |
| **UV (Rust)** | Entorno reproducible y determinista |

---

## Capacidades Clave

- **Extracción automatizada**: Playwright con autenticación híbrida (asistida + headless) y persistencia de sesión en `localStorage`, evitando store credenciales y sorteando bloqueos CORS/WAF.
- **Conciliación de retenciones**: Algoritmo que agrupa devengados netos con sus retenciones (ej. 8% de renta) para reconstruir el monto bruto real por mes y evitar falsos duplicados.
- **Sistema de scoring mensual**: Evaluación multivariable (frecuencia, división exacta, regex en glosas) que deduce el monto mensual del contrato cuando no está explicitado en los metadatos.
- **Clasificación inteligente**: Árbol de decisión que categoriza cada expediente en 5 estados operativos con acción administrativa sugerida.

---

## Clasificación de Estados

```
┌─────────────┐
│   Inicio    │
└──────┬──────┘
       │
       ▼
┌───────────────┐
│ ¿Hay          │
│ devengados?   │
└───────┬───────┘
   ┌────┴────┐
   │ No      │ Sí
   ▼         ▼
┌────────┐ ┌────────────────┐
│¿Monto  │ │ ¿Devengado ==  │
│final=0?│ │ Monto final?   │
└───┬────┘ └───┬────────────┘
   ┌┴┐       ┌──┴──┐
   │Sí│       │ Sí  │ No
   ▼  ▼       ▼     ▼
┌────────┐ ┌──────────┐ ┌──────────────┐
│rebaja  │ │¿Hubo     │ │¿Saldo y      │
│_total  │ │rebaja?   │ │plazo vencido?│
└────────┘ └──┬───┬───┘ └──┬───┬───────┘
            ┌─┴┐ ┌┴─┐    ┌─┴┐ ┌┴─┐
            │Sí│ │No│    │Sí│ │No│
            ▼  │ ▼  │    ▼  │ ▼  │
         ┌────┐│┌────┐│ ┌────┐│┌────┐
         │reb.│││con-││ │por │││vi- │
         │par.│││clu.││ │re- │││gen-│
         └────┘│└────┘│ └────┘│└────┘
               └──────┘       └──────┘
```

| Estado | Significado | Acción sugerida |
|---|---|---|
| **Concluida** | Devengado = Monto final | Archivar expediente |
| **Rebaja parcial** | Se redujo el presupuesto y se ejecutó el saldo | Registrar como conciliado |
| **Rebaja total** | Orden cancelada sin devengados | Confirmar anulación |
| **Por rebajar** | Plazo vencido con saldo remanente | Liberar presupuesto no ejecutado |
| **Vigente** | Saldo a favor y en plazo de ejecución | Monitorear entregables |

---

## Valor de Negocio

- **Optimización presupuestal**: Detecta automáticamente saldos comprometidos no ejecutables para liberarlos y reasignarlos a partidas con necesidad de liquidez.
- **Eficiencia operativa**: Reduce de horas a minutos la auditoría de cientos de expedientes gracias a la extracción automatizada y persistencia de sesión.
- **Trazabilidad financiera**: Reporte Excel con devengados agrupados que sirve como registro de conciliación transparente para auditorías internas o de la Contraloría.
