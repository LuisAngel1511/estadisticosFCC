import os, re, unicodedata
import pandas as pd
import psycopg2

RUTA_SS = "data/ss.xlsx"
RUTA_PP = "data/pp.xlsx"

def clean_text(s: str) -> str:
    if pd.isna(s): return ""
    s = str(s).strip()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_for_matching(s: str) -> str:
    s = clean_text(s).upper()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^A-Z0-9 ]+", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

# Ajusta tu unificación
empresa_map = {
    "BENEMERITA UNIVERSIDAD AUTONOMA DE PUEBLA": "Benemérita Universidad Autónoma de Puebla",
    "COORDINACION GENERAL DE DESARROLLO SUSTENTABLE": "Coordinación General de Desarrollo Sustentable",
    "FACULTAD DE CIENCIAS DE LA COMPUTACION": "Facultad de Ciencias de la Computación",
}

def empresa_final(nombre: str) -> str:
    key = normalize_for_matching(nombre)
    return empresa_map.get(key, clean_text(nombre))

def main():
    dsn = os.environ["DATABASE_URL"]
    conn = psycopg2.connect(dsn, sslmode="require")
    conn.autocommit = False

    # Lee excel y concat
    df_ss = pd.read_excel(RUTA_SS); df_ss["Tipo"] = "SS"
    df_pp = pd.read_excel(RUTA_PP); df_pp["Tipo"] = "PP"
    df = pd.concat([df_ss, df_pp], ignore_index=True)
    df.columns = [c.strip() for c in df.columns]
    df["Dependencia"] = df["Dependencia"].apply(empresa_final)

    rubros_cols = [c for c in df.columns if c.startswith("R") and c[1:3].isdigit()]
    rubros_cols = sorted(rubros_cols)

    # Inserta rubros (id=R01..R15, nombre=texto de tu columna)
    with conn.cursor() as cur:
        for col in rubros_cols:
            rubro_id = col[:3]  # 'R01'
            cur.execute(
                "INSERT INTO rubros (id, nombre) VALUES (%s,%s) ON CONFLICT (id) DO UPDATE SET nombre=EXCLUDED.nombre;",
                (rubro_id, col)
            )
        conn.commit()

    # Inserta datos
    with conn.cursor() as cur:
        for i, row in df.iterrows():
            alumno_id = f"A{str(i+1).zfill(5)}"  # ID artificial (sin PII)

            empresa = row["Dependencia"]
            tipo = row["Tipo"]
            promedio_final = float(row["Promedio_Final"]) if "Promedio_Final" in row and pd.notna(row["Promedio_Final"]) else None

            # alumnos
            cur.execute("INSERT INTO alumnos (id) VALUES (%s) ON CONFLICT DO NOTHING;", (alumno_id,))

            # empresas
            cur.execute("INSERT INTO empresas (nombre) VALUES (%s) ON CONFLICT (nombre) DO UPDATE SET nombre=EXCLUDED.nombre RETURNING id;", (empresa,))
            empresa_id = cur.fetchone()[0]

            # evaluaciones
            cur.execute("""
                INSERT INTO evaluaciones (alumno_id, empresa_id, tipo, promedio_final)
                VALUES (%s,%s,%s,%s)
                ON CONFLICT (alumno_id, tipo) DO UPDATE
                SET empresa_id=EXCLUDED.empresa_id, promedio_final=EXCLUDED.promedio_final
                RETURNING id;
            """, (alumno_id, empresa_id, tipo, promedio_final))
            eval_id = cur.fetchone()[0]

            # calificaciones
            for col in rubros_cols:
                rubro_id = col[:3]
                val = row[col]
                if pd.isna(val):
                    continue
                cur.execute("""
                    INSERT INTO calificaciones (evaluacion_id, rubro_id, calificacion)
                    VALUES (%s,%s,%s)
                    ON CONFLICT (evaluacion_id, rubro_id) DO UPDATE
                    SET calificacion=EXCLUDED.calificacion;
                """, (eval_id, rubro_id, float(val)))

        conn.commit()

    conn.close()
    print("✅ Importación completa")

if __name__ == "__main__":
    main()
