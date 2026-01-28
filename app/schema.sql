-- Empresas
CREATE TABLE IF NOT EXISTS empresas (
  id SERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE
);

-- Alumnos (sin PII, solo ID)
CREATE TABLE IF NOT EXISTS alumnos (
  id TEXT PRIMARY KEY
);

-- Evaluaciones (1 alumno = 1 registro por tipo; si quieres forzar 1 total, ajustamos)
CREATE TABLE IF NOT EXISTS evaluaciones (
  id BIGSERIAL PRIMARY KEY,
  alumno_id TEXT NOT NULL REFERENCES alumnos(id) ON DELETE RESTRICT,
  empresa_id INT NOT NULL REFERENCES empresas(id) ON DELETE RESTRICT,
  tipo TEXT NOT NULL CHECK (tipo IN ('SS','PP')),
  promedio_final NUMERIC(6,2),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (alumno_id, tipo) -- un alumno no repite SS o PP
);

-- Rubros (R01..R15)
CREATE TABLE IF NOT EXISTS rubros (
  id TEXT PRIMARY KEY,     -- 'R01'...'R15'
  nombre TEXT NOT NULL
);

-- Calificaciones (una fila por rubro evaluado)
CREATE TABLE IF NOT EXISTS calificaciones (
  evaluacion_id BIGINT NOT NULL REFERENCES evaluaciones(id) ON DELETE CASCADE,
  rubro_id TEXT NOT NULL REFERENCES rubros(id) ON DELETE RESTRICT,
  calificacion NUMERIC(6,2) NOT NULL,
  PRIMARY KEY (evaluacion_id, rubro_id)
);

-- Índices útiles para estadísticas
CREATE INDEX IF NOT EXISTS idx_eval_tipo_empresa ON evaluaciones(tipo, empresa_id);
CREATE INDEX IF NOT EXISTS idx_calif_rubro ON calificaciones(rubro_id);
