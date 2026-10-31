"""
analizar.py
Lee datos.csv (descargado por descargar.py), valida su contenido y genera
public/index.html con el informe.

Reglas de validacion, segun la consigna:
  - Si falta alguna columna obligatoria, el programa se detiene (dato
    indispensable invalido a nivel de estructura).
  - Cada fila se valida individualmente (fecha interpretable, magnitud
    numerica). Una fila invalida se descarta (no se "arregla" ni se
    sustituye por 0) y se avisa por stderr.
  - Si despues de filtrar type == "earthquake" y descartar filas invalidas
    no queda ningun sismo valido, eso SI es un dato indispensable faltante
    y el programa se detiene con un mensaje claro.
  - No se suman magnitudes (no tiene sentido fisico); se reporta la maxima.
"""
import csv
import html
import sys
from datetime import datetime, timezone

ARCHIVO_ENTRADA = "datos.csv"
DIRECTORIO_SALIDA = "public"
ARCHIVO_SALIDA = f"{DIRECTORIO_SALIDA}/index.html"

NOMBRE_ESTUDIANTE = "Fabio Mavric"
URL_FUENTE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_week.csv"
URL_REPO = "https://github.com/FabioMav/monitor-sismos-actions"
URL_ACTIONS = f"{URL_REPO}/actions"

COLUMNAS_OBLIGATORIAS = ["time", "mag", "place", "id", "type"]


class DatoIndispensableInvalido(Exception):
    """Se usa cuando falta un dato sin el cual el informe no se puede armar."""


def leer_filas(ruta_csv: str) -> list[dict]:
    try:
        with open(ruta_csv, newline="", encoding="utf-8") as f:
            lector = csv.DictReader(f)
            columnas = lector.fieldnames or []
            faltantes = [c for c in COLUMNAS_OBLIGATORIAS if c not in columnas]
            if faltantes:
                raise DatoIndispensableInvalido(
                    f"Faltan columnas obligatorias en {ruta_csv}: {', '.join(faltantes)}"
                )
            return list(lector)
    except FileNotFoundError as exc:
        raise DatoIndispensableInvalido(f"No se encontro {ruta_csv}. Corre descargar.py primero.") from exc


def validar_magnitud(valor) -> float:
    """Convierte a float; lanza ValueError con mensaje claro si no es numerico."""
    if valor is None or str(valor).strip() == "":
        raise ValueError("magnitud vacia")
    try:
        return float(valor)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"magnitud no numerica: {valor!r}") from exc


def parsear_fecha_utc(valor) -> datetime:
    """Interpreta el campo 'time' del USGS (ISO 8601, p. ej. 2026-10-30T12:34:56.789Z) como UTC."""
    if valor is None or str(valor).strip() == "":
        raise ValueError("fecha vacia")
    texto = str(valor).strip()
    if texto.endswith("Z"):
        texto = texto[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(texto)
    except ValueError as exc:
        raise ValueError(f"fecha no interpretable: {valor!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def procesar_sismos(filas: list[dict]) -> list[dict]:
    """Filtra type == 'earthquake', valida cada fila y descarta las invalidas
    (sin sustituir nada por 0). Devuelve una lista de dicts con 'dt' (datetime
    UTC) y 'mag' (float) ya validados, mas los campos originales."""
    validos = []
    descartados = 0
    for fila in filas:
        if (fila.get("type") or "").strip().lower() != "earthquake":
            continue
        try:
            mag = validar_magnitud(fila.get("mag"))
            dt = parsear_fecha_utc(fila.get("time"))
        except ValueError as exc:
            descartados += 1
            print(f"AVISO: fila descartada (id={fila.get('id', '?')}): {exc}", file=sys.stderr)
            continue
        validos.append({**fila, "mag": mag, "dt": dt})

    if descartados:
        print(f"AVISO: se descartaron {descartados} fila(s) con datos invalidos.", file=sys.stderr)

    if not validos:
        raise DatoIndispensableInvalido(
            "No quedo ningun sismo valido (type=earthquake, fecha y magnitud validas) tras la validacion."
        )
    return validos


def construir_svg_barras(conteo_por_fecha: dict) -> str:
    """Grafico de barras simple (SVG inline, sin dependencias) de sismos por fecha UTC."""
    if not conteo_por_fecha:
        return "<p>No hay datos suficientes para el grafico.</p>"
    fechas = sorted(conteo_por_fecha.keys())
    valores = [conteo_por_fecha[f] for f in fechas]
    maximo = max(valores) if valores else 1
    ancho_barra = 48
    espacio = 14
    alto_grafico = 180
    margen_inferior = 46
    ancho_svg = len(fechas) * (ancho_barra + espacio) + espacio
    alto_svg = alto_grafico + margen_inferior

    barras = []
    for i, fecha in enumerate(fechas):
        valor = conteo_por_fecha[fecha]
        alto_barra = (valor / maximo) * (alto_grafico - 20) if maximo else 0
        x = espacio + i * (ancho_barra + espacio)
        y = alto_grafico - alto_barra
        barras.append(
            f'<rect x="{x}" y="{y:.1f}" width="{ancho_barra}" height="{alto_barra:.1f}" '
            f'fill="#2a78d6" rx="3"></rect>'
            f'<text x="{x + ancho_barra / 2}" y="{y - 6:.1f}" font-size="12" '
            f'text-anchor="middle" fill="#0b0b0b">{valor}</text>'
            f'<text x="{x + ancho_barra / 2}" y="{alto_grafico + 16}" font-size="11" '
            f'text-anchor="middle" fill="#52514e">{html.escape(fecha)}</text>'
        )
    return (
        f'<svg viewBox="0 0 {ancho_svg} {alto_svg}" width="100%" '
        f'style="max-width:{ancho_svg}px; height:auto;" role="img" '
        f'aria-label="Sismos por fecha (UTC)">' + "".join(barras) + "</svg>"
    )


def generar_html(sismos: list[dict], hora_descarga_utc: datetime) -> str:
    total = len(sismos)
    mag_maxima = max(s["mag"] for s in sismos)
    mas_reciente = max(sismos, key=lambda s: s["dt"])

    diez_mas_recientes = sorted(sismos, key=lambda s: s["dt"], reverse=True)[:10]
    filas_tabla = "\n".join(
        f"<tr><td>{s['dt'].strftime('%Y-%m-%d %H:%M:%S')} UTC</td>"
        f"<td>{html.escape(s.get('place') or '(sin ubicacion)')}</td>"
        f"<td>{s['mag']:.1f}</td></tr>"
        for s in diez_mas_recientes
    )

    conteo_por_fecha: dict[str, int] = {}
    for s in sismos:
        clave = s["dt"].strftime("%Y-%m-%d")
        conteo_por_fecha[clave] = conteo_por_fecha.get(clave, 0) + 1
    svg_grafico = construir_svg_barras(conteo_por_fecha)

    fecha_min = min(s["dt"] for s in sismos).strftime("%Y-%m-%d %H:%M:%S")
    fecha_max_periodo = max(s["dt"] for s in sismos).strftime("%Y-%m-%d %H:%M:%S")

    return f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Monitor de sismos recientes</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, sans-serif; max-width: 860px; margin: 2rem auto; padding: 0 1rem;
          line-height: 1.5; color: #0b0b0b; background: #fcfcfb; }}
  @media (prefers-color-scheme: dark) {{
    body {{ color: #f0efec; background: #1a1a19; }}
    td, th {{ border-color: #3a3a38 !important; }}
  }}
  h1 {{ margin-bottom: 0.2rem; }}
  .subtitulo {{ color: #52514e; margin-top: 0; }}
  .indicadores {{ display: flex; gap: 1.5rem; flex-wrap: wrap; margin: 1.5rem 0; }}
  .indicador {{ background: rgba(42,120,214,0.08); border-radius: 10px; padding: 0.8rem 1.2rem; min-width: 160px; }}
  .indicador .valor {{ font-size: 1.6rem; font-weight: 700; }}
  .indicador .etiqueta {{ font-size: 0.85rem; color: #52514e; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1rem 0; }}
  th, td {{ border: 1px solid #d8d6d0; padding: 0.4rem 0.6rem; text-align: left; font-size: 0.92rem; }}
  th {{ background: rgba(42,120,214,0.08); }}
  footer {{ margin-top: 2rem; font-size: 0.85rem; color: #52514e; }}
  a {{ color: #2a78d6; }}
</style>
</head>
<body>
  <h1>Monitor de sismos recientes</h1>
  <p class="subtitulo">{html.escape(NOMBRE_ESTUDIANTE)} &middot;
    Fuente: <a href="{URL_FUENTE}">USGS - sismos magnitud &ge;2.5, ultimos 7 dias</a></p>

  <p>Consulta realizada: <strong>{hora_descarga_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC</strong><br>
     Periodo de los datos: {fecha_min} UTC a {fecha_max_periodo} UTC</p>

  <div class="indicadores">
    <div class="indicador"><div class="valor">{total}</div><div class="etiqueta">Sismos registrados</div></div>
    <div class="indicador"><div class="valor">{mag_maxima:.1f}</div><div class="etiqueta">Magnitud maxima</div></div>
    <div class="indicador"><div class="valor">{mas_reciente['dt'].strftime('%Y-%m-%d %H:%M')} UTC</div><div class="etiqueta">Evento mas reciente</div></div>
  </div>

  <h2>Sismos por fecha (UTC)</h2>
  {svg_grafico}

  <h2>Los 10 sismos mas recientes</h2>
  <table>
    <thead><tr><th>Fecha y hora (UTC)</th><th>Ubicacion</th><th>Magnitud</th></tr></thead>
    <tbody>
    {filas_tabla}
    </tbody>
  </table>

  <footer>
    <p>
      <a href="{URL_REPO}">Repositorio en GitHub</a> &middot;
      <a href="{URL_ACTIONS}">Historial de ejecuciones (Actions)</a>
    </p>
    <p>Generado automaticamente por GitHub Actions a partir del feed publico del USGS.</p>
  </footer>
</body>
</html>
"""


def main() -> None:
    try:
        filas = leer_filas(ARCHIVO_ENTRADA)
        sismos = procesar_sismos(filas)
    except DatoIndispensableInvalido as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    import os
    os.makedirs(DIRECTORIO_SALIDA, exist_ok=True)

    hora_descarga_utc = datetime.now(timezone.utc)
    contenido = generar_html(sismos, hora_descarga_utc)
    with open(ARCHIVO_SALIDA, "w", encoding="utf-8") as f:
        f.write(contenido)

    print(f"OK: {ARCHIVO_SALIDA} generado con {len(sismos)} sismos validos.")


if __name__ == "__main__":
    main()
