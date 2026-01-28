from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from .db import get_conn

app = FastAPI(title="Estadisticos FCC API")

# Permite que tu dashboard (static site) consuma la API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # luego lo cerramos a tu dominio Render
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/rubros")
def rubros():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, nombre FROM rubros ORDER BY id;")
            return cur.fetchall()

@app.get("/stats")
def stats(
    tipo: str = Query(..., pattern="^(SS|PP)$"),
    rubro_id: str = Query(..., pattern="^R\\d{2}$")
):
    """
    Devuelve lista de empresas con:
    - promedio del rubro
    - n (conteo)
    Ordenado desc por promedio
    """
    sql = """
    SELECT e.nombre AS empresa,
           COUNT(*)::int AS n,
           ROUND(AVG(c.calificacion)::numeric, 2) AS promedio
    FROM calificaciones c
    JOIN evaluaciones ev ON ev.id = c.evaluacion_id
    JOIN empresas e ON e.id = ev.empresa_id
    WHERE ev.tipo = %s AND c.rubro_id = %s
    GROUP BY e.nombre
    ORDER BY promedio DESC NULLS LAST, n DESC, e.nombre ASC;
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (tipo, rubro_id))
            return cur.fetchall()
