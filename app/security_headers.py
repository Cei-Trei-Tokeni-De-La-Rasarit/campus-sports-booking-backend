"""Antetele de securitate adăugate la fiecare răspuns al API-ului (KAN-126).

Browserul folosește aceste antete ca a doua linie de apărare:
- `X-Content-Type-Options: nosniff`: nu „ghicește” tipul unui fișier, deci un
  răspuns JSON nu poate fi executat ca script;
- `X-Frame-Options: DENY` și `frame-ancestors 'none'`: paginile nu pot fi puse
  într-un iframe pe alt site (atacul de tip clickjacking);
- `Referrer-Policy: no-referrer`: adresa nu se trimite mai departe altor site-uri;
- `Content-Security-Policy`: ce resurse are voie să încarce o pagină. API-ul
  întoarce doar JSON, deci nu are voie să încarce nimic (`default-src 'none'`).
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# CSP-ul pentru răspunsurile obișnuite ale API-ului (JSON).
API_CSP = "default-src 'none'; frame-ancestors 'none'"

# Documentația (Swagger la /docs, ReDoc la /redoc) este o pagină HTML care
# încarcă scripturi și stiluri de pe cdn.jsdelivr.net și are un script în
# pagină; fără aceste permisiuni, pagina ar rămâne goală.
DOCS_CSP = (
    "default-src 'none'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net "
    "https://fonts.googleapis.com; "
    "font-src https://fonts.gstatic.com; "
    "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly; "
    "connect-src 'self'; "
    "worker-src blob:; "
    "frame-ancestors 'none'"
)
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc"})

COMMON_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}


class SecurityHeadersMiddleware:
    """Middleware ASGI care adaugă antetele de securitate la fiecare răspuns.

    Lucrează direct la nivel ASGI (nu cu BaseHTTPMiddleware), cum recomandă
    Starlette: antetele se pun în momentul în care pleacă începutul
    răspunsului, deci și pe erori, pe răspunsurile CORS și pe cele trimise
    pe bucăți.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        csp = DOCS_CSP if scope["path"] in DOCS_PATHS else API_CSP

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in COMMON_HEADERS.items():
                    headers[name] = value
                headers["Content-Security-Policy"] = csp
            await send(message)

        await self.app(scope, receive, send_with_headers)
