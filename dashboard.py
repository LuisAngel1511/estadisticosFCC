import os
import re
import json
import unicodedata
from pathlib import Path

import pandas as pd
import plotly


# =========================
# Configuración
# =========================
RUTA_SS = "data/ss.xlsx"
RUTA_PP = "data/pp.xlsx"
OUT_HTML = "output/dashboard.html"
TOP_BOTTOM_N = 5


# =========================
# Utilidades
# =========================
def clean_text(s: str) -> str:
    if pd.isna(s):
        return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_for_matching(s: str) -> str:
    s = clean_text(s).upper()
    s = "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    )
    s = re.sub(r"[^A-Z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# =========================
# 1. Cargar datos
# =========================
df_ss = pd.read_excel(RUTA_SS)
df_pp = pd.read_excel(RUTA_PP)

df_ss["Tipo"] = "SS"
df_pp["Tipo"] = "PP"

df = pd.concat([df_ss, df_pp], ignore_index=True)
df.columns = [c.strip() for c in df.columns]

df["Dependencia"] = df["Dependencia"].apply(clean_text)
df["Dependencia_norm"] = df["Dependencia"].apply(normalize_for_matching)

rubros = [c for c in df.columns if c.startswith("R") and c[1:3].isdigit()]
rubros = sorted(rubros)

for col in rubros:
    df[col] = pd.to_numeric(df[col], errors="coerce")


# =========================
# 2. Unificar empresas
# =========================
empresa_map = {
    "BENEMERITA UNIVERSIDAD AUTONOMA DE PUEBLA": "Benemérita Universidad Autónoma de Puebla",
    "COORDINACION GENERAL DE DESARROLLO SUSTENTABLE": "Coordinación General de Desarrollo Sustentable",
    "FACULTAD DE CIENCIAS DE LA COMPUTACION": "Facultad de Ciencias de la Computación",
}


def empresa_final(row):
    key = row["Dependencia_norm"]
    if key in empresa_map:
        return empresa_map[key]
    return row["Dependencia"]


df["Empresa_Final"] = df.apply(empresa_final, axis=1)


# =========================
# 3. Precalcular datos para el dashboard
# =========================
data = {}

for tipo in ["SS", "PP"]:
    df_tipo = df[df["Tipo"] == tipo]
    data[tipo] = {}

    for rubro in rubros:
        tmp = (
            df_tipo.groupby("Empresa_Final")[rubro]
            .agg(n="count", promedio="mean")
            .dropna()
            .sort_values("promedio", ascending=False)
            .reset_index()
        )

        rows = []
        for _, r in tmp.iterrows():
            rows.append({
                "empresa": r["Empresa_Final"],
                "promedio": float(round(r["promedio"], 4)),
                "n": int(r["n"])
            })

        data[tipo][rubro] = rows


default_tipo = "SS" if "SS" in data else list(data.keys())[0]
default_rubro = rubros[0]


# =========================
# 4. Generar HTML
# =========================
os.makedirs("output", exist_ok=True)

plotly_js = plotly.offline.get_plotlyjs()
data_json = json.dumps(data, ensure_ascii=False)
rubros_json = json.dumps(rubros, ensure_ascii=False)

html = f"""
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <title>Dashboard Estadísticos SS / PP</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 16px;
    }}
    .card {{
      border: 1px solid #ddd;
      border-radius: 10px;
      padding: 12px;
      margin-bottom: 16px;
      box-shadow: 0 1px 6px rgba(0,0,0,0.08);
    }}
    select {{
      padding: 8px;
      margin-right: 12px;
    }}
    #chart {{
      width: 100%;
      min-height: 560px;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      border-bottom: 1px solid #eee;
      padding: 6px;
    }}
    th {{
      background: #fafafa;
    }}
  </style>
</head>
<body>

<h2>Dashboard de Estadísticos – Servicio Social y Prácticas Profesionales</h2>

<div class="card">
  <label>Tipo:</label>
  <select id="tipoSelect"></select>

  <label>Rubro:</label>
  <select id="rubroSelect"></select>

  <span id="meta" style="margin-left:16px;color:#555;"></span>
</div>

<div class="card">
  <div id="chart"></div>
</div>

<div class="card">
  <h3>Top / Bottom</h3>
  <div id="topBottom"></div>
</div>

<script>
{plotly_js}
</script>

<script>
var DATA = {data_json};
var RUBROS = {rubros_json};
var TOPN = {TOP_BOTTOM_N};

var tipoSelect = document.getElementById("tipoSelect");
var rubroSelect = document.getElementById("rubroSelect");
var meta = document.getElementById("meta");

function initSelects() {{
  for (var t in DATA) {{
    var opt = document.createElement("option");
    opt.value = t;
    opt.textContent = t;
    tipoSelect.appendChild(opt);
  }}

  for (var i = 0; i < RUBROS.length; i++) {{
    var opt2 = document.createElement("option");
    opt2.value = RUBROS[i];
    opt2.textContent = RUBROS[i];
    rubroSelect.appendChild(opt2);
  }}

  tipoSelect.value = "{default_tipo}";
  rubroSelect.value = "{default_rubro}";
}}

function render() {{
  var tipo = tipoSelect.value;
  var rubro = rubroSelect.value;

  var rows = DATA[tipo][rubro];

  var empresas = [];
  var promedios = [];
  var textos = [];
  var totalReg = 0;

  for (var i = 0; i < rows.length; i++) {{
    empresas.push(rows[i].empresa);
    promedios.push(rows[i].promedio);
    textos.push("n=" + rows[i].n);
    totalReg += rows[i].n;
  }}

  meta.innerHTML =
    "<b>Empresas:</b> " + rows.length +
    " | <b>Registros:</b> " + totalReg;

  var trace = {{
    type: "bar",
    orientation: "h",
    y: empresas.slice().reverse(),
    x: promedios.slice().reverse(),
    text: textos.slice().reverse(),
    hovertemplate:
      "<b>%{{y}}</b><br>Promedio: %{{x}}<br>%{{text}}<extra></extra>"
  }};

  var layout = {{
    title: tipo + " - Promedio por empresa - " + rubro,
    margin: {{ l: 260, r: 30, t: 50, b: 50 }},
    xaxis: {{ title: "Promedio" }},
    yaxis: {{ automargin: true }}
  }};

  Plotly.newPlot("chart", [trace], layout);

  var top = rows.slice(0, TOPN);
  var bottom = rows.slice(Math.max(rows.length - TOPN, 0));

  function table(title, arr) {{
    var h = "<h4>" + title + "</h4><table><tr><th>Empresa</th><th>Promedio</th><th>n</th></tr>";
    for (var i = 0; i < arr.length; i++) {{
      h += "<tr><td>" + arr[i].empresa + "</td><td>" +
           arr[i].promedio.toFixed(2) + "</td><td>" +
           arr[i].n + "</td></tr>";
    }}
    h += "</table>";
    return h;
  }}

  document.getElementById("topBottom").innerHTML =
    table("Top " + TOPN, top) + "<br/>" +
    table("Bottom " + TOPN, bottom);
}}

tipoSelect.addEventListener("change", render);
rubroSelect.addEventListener("change", render);

initSelects();
render();
</script>

</body>
</html>
"""

with open(OUT_HTML, "w", encoding="utf-8") as f:
    f.write(html)

print("✅ Dashboard generado correctamente:")
print(OUT_HTML)
print("Ábrelo con doble clic en el navegador.")
