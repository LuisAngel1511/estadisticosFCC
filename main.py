import os
import re
import shutil
import unicodedata
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

# =========================
# Config
# =========================
RUTA_SS = "data/ss.xlsx"
RUTA_PP = "data/pp.xlsx"

# Graficado
PAGE_SIZE = 25  # empresas por imagen (para incluir TODAS sin que sea ilegible)
TOP_BOTTOM_N = 5  # Top/Bottom por rubro para el excel de ranking

# =========================
# Utilidades
# =========================
def clean_text(s: str) -> str:
    """Quita espacios extra y normaliza espacios."""
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_for_matching(s: str) -> str:
    """
    Normalización agresiva para detectar duplicados:
    - mayúsculas
    - sin acentos
    - solo letras/números/espacio
    """
    s = clean_text(s).upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def slugify(nombre: str) -> str:
    nombre = normalize_for_matching(nombre).replace(" ", "_")
    return nombre[:60] if nombre else "SIN_NOMBRE"

def safe_folder_name(s: str) -> str:
    """Nombre de carpeta seguro para Windows."""
    s = clean_text(s)
    s = re.sub(r'[<>:"/\\|?*]', "", s)
    s = s.strip().rstrip(".")
    return s[:80] if s else "SIN_NOMBRE"

# =========================
# 0. Crear carpetas de salida
# =========================
os.makedirs("output/reportes", exist_ok=True)
os.makedirs("output/graficas", exist_ok=True)
Path("output/empresas").mkdir(parents=True, exist_ok=True)

# =========================
# 1. Cargar archivos
# =========================
df_ss = pd.read_excel(RUTA_SS)
df_pp = pd.read_excel(RUTA_PP)

# Forzar Tipo por archivo (más confiable)
df_ss["Tipo"] = "SS"
df_pp["Tipo"] = "PP"

df = pd.concat([df_ss, df_pp], ignore_index=True)

# =========================
# 2. Limpiar nombres de columnas (quita espacios al final/inicio)
# =========================
df.columns = [c.strip() for c in df.columns]

# =========================
# 3. Limpiar empresa (Dependencia) y preparar normalizada
# =========================
df["Dependencia"] = df["Dependencia"].apply(clean_text)
df["Dependencia_norm"] = df["Dependencia"].apply(normalize_for_matching)

# =========================
# 4. Detectar rubros y convertir a numérico
# =========================
rubros = [c for c in df.columns if c.startswith("R") and len(c) >= 3 and c[1:3].isdigit()]
rubros = sorted(rubros)  # R01..R15

for col in rubros + ["Promedio_Final"]:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

# =========================
# 5. Validaciones rápidas
# =========================
print("Filas totales:", df.shape[0])
print("Rubros detectados:", rubros)

faltantes = df[rubros + ["Promedio_Final"]].isna().sum().sort_values(ascending=False)
print("\nValores faltantes por columna (top):")
print(faltantes.head(10))

print("\nEmpresas únicas (texto original):", df["Dependencia"].nunique())
print("Empresas únicas (normalizado):", df["Dependencia_norm"].nunique())

dup_groups = (
    df.groupby("Dependencia_norm")["Dependencia"]
      .unique()
      .apply(list)
)
posibles = dup_groups[dup_groups.apply(lambda x: len(x) > 1)]
print("\nPosibles empresas duplicadas por escritura (normalización):")
if len(posibles) == 0:
    print("No se detectaron duplicados obvios.")
else:
    for norm, variantes in posibles.items():
        print(f"- {norm}: {variantes}")

# =========================
# 6. Unificar empresas duplicadas (manual map)
# =========================
empresa_map = {
    "BENEMERITA UNIVERSIDAD AUTONOMA DE PUEBLA": "Benemérita Universidad Autónoma de Puebla",
    "COORDINACION GENERAL DE DESARROLLO SUSTENTABLE": "Coordinación General de Desarrollo Sustentable",
    "FACULTAD DE CIENCIAS DE LA COMPUTACION": "Facultad de Ciencias de la Computación",
}

def empresa_final(row) -> str:
    clave = row["Dependencia_norm"]
    if clave in empresa_map:
        return empresa_map[clave]
    return row["Dependencia"]

df["Empresa_Final"] = df.apply(empresa_final, axis=1)

# =========================
# 7. Estadísticos por empresa y tipo
# =========================
estadisticos = (
    df.groupby(["Empresa_Final", "Tipo"])[rubros]
      .agg(["count", "mean", "median", "std"])
      .round(2)
)
estadisticos.to_excel("output/reportes/estadisticos_por_rubro.xlsx")
print("\n✅ Archivo generado: output/reportes/estadisticos_por_rubro.xlsx")

# =========================
# 8. Ranking Top/Bottom por rubro (incluye TODAS las empresas)
# =========================
resumen_rankings = []

for tipo in ["SS", "PP"]:
    df_tipo = df[df["Tipo"] == tipo].copy()
    if df_tipo.empty:
        continue

    for rubro in rubros:
        tmp = (
            df_tipo.groupby("Empresa_Final")[rubro]
                  .agg(n="count", promedio="mean")
                  .dropna()
        )
        if tmp.empty:
            continue

        tmp = tmp.sort_values("promedio", ascending=False)

        topN = tmp.head(TOP_BOTTOM_N).reset_index()
        topN["Tipo"] = tipo
        topN["Rubro"] = rubro
        topN["Ranking"] = f"Top {TOP_BOTTOM_N}"

        bottomN = tmp.tail(TOP_BOTTOM_N).reset_index()
        bottomN["Tipo"] = tipo
        bottomN["Rubro"] = rubro
        bottomN["Ranking"] = f"Bottom {TOP_BOTTOM_N}"

        resumen_rankings.append(topN)
        resumen_rankings.append(bottomN)

if resumen_rankings:
    ranking_df = pd.concat(resumen_rankings, ignore_index=True)
    ranking_df.to_excel("output/reportes/rankings_top_bottom_por_rubro.xlsx", index=False)
    print("✅ Excel generado: output/reportes/rankings_top_bottom_por_rubro.xlsx")
else:
    print("⚠️ No se generó ranking (revisa datos).")

# =========================
# 9. Gráficas por rubro comparando empresas (TODAS, paginadas)
# =========================
for tipo in ["SS", "PP"]:
    df_tipo = df[df["Tipo"] == tipo].copy()
    if df_tipo.empty:
        print(f"⚠️ No hay datos para tipo {tipo}")
        continue

    for rubro in rubros:
        tmp = (
            df_tipo.groupby("Empresa_Final")[rubro]
                  .agg(n="count", promedio="mean")
                  .dropna()
        )
        if tmp.empty:
            continue

        tmp = tmp.sort_values("promedio", ascending=False)

        total = len(tmp)
        paginas = (total + PAGE_SIZE - 1) // PAGE_SIZE

        for p in range(paginas):
            ini = p * PAGE_SIZE
            fin = min((p + 1) * PAGE_SIZE, total)

            # trozo de esa página
            tmp_plot = tmp.iloc[ini:fin].copy()
            # ordenar ascendente para barh (para que el mayor quede arriba al invertir)
            tmp_plot = tmp_plot.sort_values("promedio", ascending=True)

            plt.figure(figsize=(12, max(4, 0.35 * len(tmp_plot))))
            plt.barh(tmp_plot.index, tmp_plot["promedio"])
            plt.title(
                f"{tipo} - {rubro} (promedio por empresa) | Página {p+1}/{paginas}"
            )
            plt.xlabel("Promedio")
            plt.ylabel("Empresa")

            # Nota visual: muestra n en un texto pequeño (opcional)
            # (Si quieres etiquetas n por barra, dime y lo añadimos)
            plt.tight_layout()

            out_png = f"output/graficas/{tipo}_{slugify(rubro)}_pag{p+1}de{paginas}.png"
            plt.savefig(out_png, dpi=150)
            plt.close()

print("✅ Gráficas generadas en: output/graficas/")

# =========================
# 10. Paquete por empresa (reporte_empresa.xlsx)
# =========================
base_empresas = Path("output/empresas")
base_empresas.mkdir(parents=True, exist_ok=True)

# Ranking completo por rubro+tipo para consultar posición
rank_pos = []
for tipo in ["SS", "PP"]:
    df_tipo = df[df["Tipo"] == tipo].copy()
    if df_tipo.empty:
        continue

    for rubro in rubros:
        tmp = (
            df_tipo.groupby("Empresa_Final")[rubro]
                  .agg(n="count", promedio="mean")
                  .dropna()
        )
        if tmp.empty:
            continue

        tmp = tmp.sort_values("promedio", ascending=False).reset_index()
        tmp["Tipo"] = tipo
        tmp["Rubro"] = rubro
        tmp["Posicion"] = range(1, len(tmp) + 1)
        tmp["Total_empresas_consideradas"] = len(tmp)

        rank_pos.append(tmp)

ranking_completo = pd.concat(rank_pos, ignore_index=True) if rank_pos else pd.DataFrame()

empresas = sorted(df["Empresa_Final"].unique())

for emp in empresas:
    carpeta = base_empresas / safe_folder_name(emp)
    carpeta.mkdir(parents=True, exist_ok=True)

    df_emp = df[df["Empresa_Final"] == emp].copy()

    resumen_emp = (
        df_emp.groupby("Tipo")[rubros]
              .agg(["count", "mean"])
              .round(2)
    )

    if not ranking_completo.empty:
        ranking_emp = ranking_completo[ranking_completo["Empresa_Final"] == emp].copy()
        ranking_emp = ranking_emp[["Tipo", "Rubro", "n", "promedio", "Posicion", "Total_empresas_consideradas"]]
        ranking_emp = ranking_emp.sort_values(["Tipo", "Rubro"])
    else:
        ranking_emp = pd.DataFrame()

    out_xlsx = carpeta / "reporte_empresa.xlsx"
    with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
        df_emp.to_excel(writer, sheet_name="Datos", index=False)
        resumen_emp.to_excel(writer, sheet_name="Resumen_promedios")
        if not ranking_emp.empty:
            ranking_emp.to_excel(writer, sheet_name="Ranking", index=False)

print("✅ Paquetes por empresa generados en: output/empresas/")
