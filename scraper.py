import os, logging
import psycopg2
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

DB_HOST = os.environ["DB_HOST"].strip()
DB_PORT = int(os.environ.get("DB_PORT", "5432").strip())
DB_NAME = os.environ["DB_NAME"].strip()
DB_USER = os.environ["DB_USER"].strip()
DB_PASSWORD = os.environ["DB_PASSWORD"].strip()

KEYWORDS = ["convocatoria", "examen", "cap", "certificado", "aptitud"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "Referer": "https://www.google.com/",
    "Connection": "keep-alive",
}

def get_conn():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD, sslmode="require"
    )

def find_pdf_links(base_url, html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        text = (a.get_text() or "").lower()
        href_lower = href.lower()
        is_doc = (
            href_lower.endswith(".pdf")
            or href_lower.endswith("/download")
            or "/medias/" in href_lower
        )
        if is_doc and any(k in href_lower or k in text for k in KEYWORDS):
            full_url = requests.compat.urljoin(base_url, href)
            titulo = a.get_text(strip=True) or href
            links.append((full_url, titulo))
    return links

def main():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select id, nombre, slug, url_fuente from comunidades_autonomas where activo = true;")
    comunidades = cur.fetchall()

    session = requests.Session()
    session.headers.update(HEADERS)

    total_nuevas = 0
    for comunidad_id, nombre, slug, url in comunidades:
        url = url.strip()
        log.info(f"Revisando {nombre} -> {url}")
        try:
            resp = session.get(url, timeout=20)
            resp.raise_for_status()
        except Exception as e:
            log.warning(f"  Error accediendo a {nombre}: {e}")
            continue

        pdfs = find_pdf_links(url, resp.text)
        log.info(f"  Encontrados {len(pdfs)} PDFs candidatos")

        for pdf_url, titulo in pdfs:
            cur.execute("select 1 from convocatorias where url_pdf = %s;", (pdf_url,))
            if cur.fetchone():
                continue
            cur.execute(
                """
                insert into convocatorias (comunidad_id, url_pdf, titulo, estado)
                values (%s, %s, %s, 'pendiente')
                """,
                (comunidad_id, pdf_url, titulo)
            )
            total_nuevas += 1
            log.info(f"  NUEVA: {titulo} -> {pdf_url}")

    conn.commit()
    log.info(f"Total convocatorias nuevas detectadas: {total_nuevas}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
