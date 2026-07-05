import os, re, logging
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

def es_convocatoria_valida(texto_o_url):
    t = texto_o_url.lower()
    tiene_aptitud_o_convocatoria = "aptitud" in t or "convocatoria" in t
    tiene_cap_o_examen = "cap" in t or "examen" in t
    return tiene_aptitud_o_convocatoria and tiene_cap_o_examen

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
            or "/documents/d/" in href_lower
            or "(pdf" in text
        )
        if is_doc and es_convocatoria_valida(href_lower + " " + text):
            full_url = requests.compat.urljoin(base_url, href)
            titulo = a.get_text(strip=True) or href
            links.append((full_url, titulo))
    return links

def find_links_from_text(text):
    urls = re.findall(r'https?://[^\s\)\]]+', text)
    links = []
    for u in urls:
        u_lower = u.lower()
        is_doc = (
            u_lower.endswith(".pdf")
            or u_lower.endswith("/download")
            or "/medias/" in u_lower
            or "/documents/d/" in u_lower
        )
        if is_doc and es_convocatoria_valida(u_lower):
            links.append((u, u))
    return links

def fetch_via_jina(url):
    proxy_url = "https://r.jina.ai/" + url
    resp = requests.get(proxy_url, timeout=30, headers={"User-Agent": HEADERS["User-Agent"]})
    resp.raise_for_status()
    return resp.text

def main():
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("select id, nombre, slug, url_fuente from comunidades_autonomas where activo = true;")
    comunidades = cur.fetchall()

    session = requests.Session()
    session.headers.update(HEADERS)

    comunidades_sin_resultados = []
    total_nuevas = 0
    for comunidad_id, nombre, slug, url in comunidades:
        url = url.strip()
        log.info(f"Revisando {nombre} -> {url}")
        pdfs = []

        try:
            resp = session.get(url, timeout=25)
            resp.raise_for_status()
            pdfs = find_pdf_links(url, resp.text)
        except requests.exceptions.SSLError as e:
            log.warning(f"  Error SSL en {nombre}, reintentando sin verificar certificado: {e}")
            try:
                resp = session.get(url, timeout=25, verify=False)
                resp.raise_for_status()
                pdfs = find_pdf_links(url, resp.text)
            except Exception as e2:
                log.warning(f"  Reintento sin SSL también fallo en {nombre}: {e2}")
        except Exception as e:
            log.warning(f"  requests directo fallo en {nombre}: {e}")

        if not pdfs:
            log.info(f"  0 resultados directos, probando via Jina Reader...")
            try:
                text = fetch_via_jina(url)
                pdfs = find_links_from_text(text)
            except Exception as e:
                log.warning(f"  Error con Jina Reader en {nombre}: {e}")

        log.info(f"  Encontrados {len(pdfs)} PDFs candidatos")

        if not pdfs:
            comunidades_sin_resultados.append(nombre)

        for pdf_url, titulo in pdfs:
            cur.execute("select 1 from convocatorias where url_pdf = %s;", (pdf_url,))
            if cur.fetchone():
                continue
            cur.execute(
                """
                insert into convocatorias (comunidad_id, url_pdf, titulo, estado)
                values (%s, %s, %s, 'publicado')

                """,
                (comunidad_id, pdf_url, titulo)
            )
            total_nuevas += 1
            log.info(f"  NUEVA: {titulo} -> {pdf_url}")

    conn.commit()
    if comunidades_sin_resultados:
        log.warning(f"Comunidades SIN resultados ({len(comunidades_sin_resultados)}): {', '.join(comunidades_sin_resultados)}")
    else:
        log.info("Todas las comunidades devolvieron al menos 1 resultado")
    log.info(f"Total convocatorias nuevas detectadas: {total_nuevas}")
    cur.close()
    conn.close()

if __name__ == "__main__":
    main()
