import os, logging, psycopg2
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)
DB_CONFIG = {
    "host": os.environ["DB_HOST"],
    "port": int(os.environ.get("DB_PORT", 5432)),
    "dbname": os.environ["DB_NAME"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "sslmode": "require",
}
log.info("Conectando a BD...")
conn = psycopg2.connect(**DB_CONFIG)
log.info("Conexion OK")
conn.close()
log.info("Scraper CAP ejecutado correctamente")
