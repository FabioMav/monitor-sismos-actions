"""
descargar.py
Consulta el CSV publico de sismos recientes (magnitud >= 2.5, ultimos 7 dias)
del USGS y lo guarda como datos.csv en el directorio actual. Se ejecuta de
cero en cada corrida (no reusa nada de corridas anteriores) y se detiene con
un error claro si la descarga falla, para que el workflow de CI falle tambien
(y asi CD no publique un sitio con datos viejos/rotos).
"""
import sys
import urllib.request
import urllib.error

URL_USGS = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.csv"
ARCHIVO_SALIDA = "datos.csv"
TIMEOUT_SEGUNDOS = 30


def descargar(url: str, destino: str) -> None:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT_SEGUNDOS) as resp:
            if resp.status != 200:
                raise RuntimeError(f"El servidor respondio con codigo {resp.status}")
            contenido = resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        print(f"ERROR: no se pudo descargar el CSV del USGS ({url}): {exc}", file=sys.stderr)
        sys.exit(1)

    if not contenido or len(contenido.strip()) == 0:
        print("ERROR: la descarga se completo pero el archivo vino vacio.", file=sys.stderr)
        sys.exit(1)

    primera_linea = contenido.split(b"\n", 1)[0].decode("utf-8", errors="replace")
    if "time" not in primera_linea or "mag" not in primera_linea:
        print(
            "ERROR: el contenido descargado no parece un CSV valido del USGS "
            f"(encabezado inesperado: {primera_linea[:120]!r}).",
            file=sys.stderr,
        )
        sys.exit(1)

    with open(destino, "wb") as f:
        f.write(contenido)

    n_lineas = contenido.count(b"\n")
    print(f"OK: descargado {destino} ({len(contenido)} bytes, ~{n_lineas} filas incluyendo encabezado).")


if __name__ == "__main__":
    descargar(URL_USGS, ARCHIVO_SALIDA)
