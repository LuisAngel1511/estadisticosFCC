import os
import psycopg2
from psycopg2.extras import RealDictCursor

def get_conn():
    # Render te da una DATABASE_URL para Postgres (la pondrás en env vars)
    dsn = os.environ["DATABASE_URL"]
    return psycopg2.connect(dsn, sslmode="require", cursor_factory=RealDictCursor)
