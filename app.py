# app.py
import os
import glob
from datetime import datetime
from flask import Flask, send_file, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import matplotlib.pyplot as plt
import xarray as xr
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import pandas as pd
import numpy as np
import geopandas as gpd
from shapely.geometry import Polygon

# Importa tus utilitarios - adapta nombres si tu estructura es diferente
from downloader import download_latest_netcdf, clean_old_files
from Prediction import run_prediction

# ---- Config ----
app = Flask(__name__)
DOWNLOAD_DIR = "crops"
PLOT_PATH = "static/last_prediction.png"
ZOOM_PATH = "static/zoom_prediction.png"
SHP_PATH = "./provincia-de-salta/provincia-de-salta-shp.shp"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs("static", exist_ok=True)

# Scheduler para correr cada 15 minutos
scheduler = BackgroundScheduler()
scheduler.start()


def safe_open_dataset(path):
    """Abrir xarray con try/except y devolver None si falla."""
    try:
        ds = xr.open_dataset(path)
        return ds
    except Exception as e:
        print(f"Error abriendo {path}: {e}")
        return None


def job():
    """
    Job principal:
    - Descarga / limpia archivos
    - Ejecuta la predicción (run_prediction)
    - Genera dos imágenes:
        1) PLOT_PATH: 3 paneles (2 inputs + predicción)
        2) ZOOM_PATH: recorte detallado sobre el shapefile (3 paneles)
    """
    print(f"{datetime.now()}: Ejecutando descarga y predicción...")

    # --- Paso 1: asegurar carpeta ---
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # --- Paso 2: descargar últimos netCDF ---
    try:
        files_downloaded = download_latest_netcdf()
        clean_old_files()
    except Exception as e:
        print("Error descargando archivos (continuamos con los existentes):", e)
        files_downloaded = []

    # Tomar los últimos 2 archivos disponibles en DOWNLOAD_DIR
    all_nc = sorted(glob.glob(os.path.join(DOWNLOAD_DIR, "*.nc")))
    if len(all_nc) == 0:
        print("No hay archivos netCDF en crops/. Abortando job.")
        return

    # usar las 2 últimas (o las disponibles si hay <2)
    files = all_nc[-2:]
    print("Usando archivos:", files)

    # --- Paso 3: generar predicción ---
    pred_file = None
    try:
        pred_file = run_prediction()  # Se asume que devuelve ruta or None
        print("run_prediction returned:", pred_file)
    except Exception as e:
        print("Error al ejecutar run_prediction():", e)
        pred_file = None

    # --- Paso 4: plot principal (2 inputs + predicción) ---
    try:
        n_inputs = len(files)
        # siempre creamos 3 paneles: 2 inputs (si no hay suficientes, mostramos mensaje) + predicción
        fig, axes = plt.subplots(1, 3, figsize=(18, 6), subplot_kw={'projection': ccrs.PlateCarree()})

        # Extensión global de interés (ajusta según necesidad)
        lon_min, lon_max = -70, -60
        lat_min, lat_max = -30, -20

        # Feature de provincias (límites)
        provincias = cfeature.NaturalEarthFeature(
            category='cultural',
            name='admin_1_states_provinces_lines',
            scale='10m',
            facecolor='none'
        )

        # Orden: el input más viejo en axes[0], luego el más nuevo en axes[1]
        for i in range(2):
            ax = axes[i]
            ax.set_extent([lon_min, lon_max, lat_min, lat_max])
            ax.add_feature(cfeature.LAND, facecolor='lightgray')
            ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
            ax.add_feature(cfeature.BORDERS, linewidth=1)
            ax.add_feature(provincias, edgecolor='black', linewidth=1)

            if i < n_inputs:
                fpath = files[i - (2 - n_inputs)] if n_inputs < 2 else files[i]  # si hay 1 archivo, mapearlo a axes[1] y axes[0] mostrar mensaje
                ds = safe_open_dataset(fpath)
                if ds is None or "DSSF_TOT" not in ds:
                    ax.text(0.5, 0.5, "Archivo inválido", ha="center", va="center", transform=ax.transAxes)
                    ax.set_title("Input inválido")
                else:
                    # Tomamos la primer time index
                    try:
                        data = ds["DSSF_TOT"].isel(time=0)
                        # Ajuste horario similar al tuyo original
                        time_input = ds.time.values[0]
                        time_adjusted = pd.to_datetime(time_input) - pd.Timedelta(minutes=180)
                        time_str = time_adjusted.strftime("%H:%M %d %b %Y")
                    except Exception:
                        data = ds["DSSF_TOT"]
                        time_str = "Input"

                    # pcolormesh (soporta lon/lat 1D o 2D)
                    try:
                        im = ax.pcolormesh(ds.lon, ds.lat, data, cmap="Oranges", shading="auto", transform=ccrs.PlateCarree())
                    except Exception:
                        # Intento con .values por si acaso
                        im = ax.pcolormesh(ds.lon.values, ds.lat.values, data.values, cmap="Oranges", shading="auto", transform=ccrs.PlateCarree())

                    ax.set_title(f"{time_str}")
                    fig.colorbar(im, ax=ax, orientation='vertical', fraction=0.046)
                    try:
                        ds.close()
                    except Exception:
                        pass
            else:
                ax.text(0.5, 0.5, "No hay input", ha="center", va="center", transform=ax.transAxes)
                ax.set_title("Input no disponible")

        # Predicción en axes[2]
        axp = axes[2]
        axp.set_extent([lon_min, lon_max, lat_min, lat_max])
        axp.add_feature(cfeature.LAND, facecolor='lightgray')
        axp.add_feature(cfeature.COASTLINE, linewidth=0.8)
        axp.add_feature(cfeature.BORDERS, linewidth=1)
        axp.add_feature(provincias, edgecolor='black', linewidth=1)

        for spine in axp.spines.values():
            spine.set_edgecolor('yellow')
            spine.set_linewidth(4.5)

        if pred_file and os.path.exists(pred_file):
            ds_pred = safe_open_dataset(pred_file)
            if ds_pred is None:
                axp.text(0.5, 0.5, "Predicción inválida", ha="center", va="center", transform=axp.transAxes)
                axp.set_title("Predicción inválida")
            else:
                try:
                    # Ajuste horario similar al original
                    time_pred = pd.to_datetime(ds_pred.coords['time'].values) + pd.Timedelta(minutes=15 - 180)
                    time_str_pred = time_pred.strftime("%H:%M %d %b %Y")
                except Exception:
                    time_str_pred = "Predicción"

                try:
                    im = axp.pcolormesh(ds_pred.lon, ds_pred.lat, ds_pred.DSSF_PRED.values, cmap="Oranges", shading="auto", transform=ccrs.PlateCarree())
                except Exception:
                    im = axp.pcolormesh(ds_pred.lon.values, ds_pred.lat.values, ds_pred.DSSF_PRED.values, cmap="Oranges", shading="auto", transform=ccrs.PlateCarree())

                axp.set_title(f"Predicción {time_str_pred}")
                fig.colorbar(im, ax=axp, orientation='vertical', fraction=0.046)
                try:
                    ds_pred.close()
                except Exception:
                    pass
        else:
            axp.text(0.5, 0.5, "No predicción", ha="center", va="center", transform=axp.transAxes)
            axp.set_title("Predicción no disponible")

        plt.tight_layout()
        plt.savefig(PLOT_PATH, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"{datetime.now()}: Plot principal guardado en {PLOT_PATH}")
    except Exception as e:
        print("Error generando plot principal:", e)

    # --- Paso 5: generar zoom/detalle usando shapefile (Salta) ---
    try:
        if not os.path.exists(SHP_PATH):
            print(f"No se encontró shapefile en {SHP_PATH}. Se omite zoom.")
            return

        gdf = gpd.read_file(SHP_PATH)
        print("Shapefile leído, geometrías:", len(gdf))

        fig, axes = plt.subplots(1, 3, figsize=(18, 6), subplot_kw={'projection': ccrs.PlateCarree()})

        # Extensión de recorte a usar (ajusta si quieres otra región dentro de Salta)
        lon_min2, lon_max2 = -68.5, -62.3
        lat_min2, lat_max2 = -26.5, -21.9

        # Inputs detallados
        for i in range(2):
            ax = axes[i]
            ax.set_extent([lon_min2, lon_max2, lat_min2, lat_max2])
            ax.coastlines(resolution="110m")
            ax.add_feature(cfeature.BORDERS.with_scale("10m"))

            if i < n_inputs:
                fpath = files[i - (2 - n_inputs)] if n_inputs < 2 else files[i]
                ds = safe_open_dataset(fpath)
                if ds is None or "DSSF_TOT" not in ds:
                    ax.text(0.5, 0.5, "Archivo inválido", ha="center", va="center", transform=ax.transAxes)
                    ax.set_title(f"Input {i+1} inválido")
                else:
                    try:
                        z = ds["DSSF_TOT"].isel(time=0)
                        time_input = ds.time.values[0]
                        time_adjusted = pd.to_datetime(time_input) - pd.Timedelta(minutes=180)
                        time_str = time_adjusted.strftime("%H:%M %d %b %Y")
                    except Exception:
                        z = ds["DSSF_TOT"]

                    try:
                        mesh = ax.pcolormesh(ds.lon, ds.lat, z, cmap='Spectral_r', shading='auto', transform=ccrs.PlateCarree(), vmin=100, vmax=1200)
                    except Exception:
                        mesh = ax.pcolormesh(ds.lon.values, ds.lat.values, z.values, cmap='Spectral_r', shading='auto', transform=ccrs.PlateCarree(), vmin=100, vmax=1200)

                    # Dibujar límites del shapefile
                    for geom in gdf.geometry:
                        polys = [geom] if isinstance(geom, Polygon) else geom.geoms
                        for poly in polys:
                            x, y = poly.exterior.xy
                            ax.plot(x, y, color="black", linewidth=0.6, transform=ccrs.PlateCarree())

                    ax.set_title(f"{time_str}")
                    fig.colorbar(mesh, ax=ax, label="GHI (W/m²)", shrink=0.7, pad=0.01)

                    try:
                        ds.close()
                    except Exception:
                        pass
            else:
                ax.text(0.5, 0.5, "No hay input", ha="center", va="center", transform=ax.transAxes)
                ax.set_title(f"Input {i+1} no disponible")

        # Predicción detallada en axes[2]
        ax = axes[2]
        ax.set_extent([lon_min2, lon_max2, lat_min2, lat_max2])
        ax.coastlines(resolution="110m")
        ax.add_feature(cfeature.BORDERS.with_scale("10m"))

        for spine in ax.spines.values():
            spine.set_edgecolor('yellow')
            spine.set_linewidth(4.5)




        if pred_file and os.path.exists(pred_file):
            ds_pred = safe_open_dataset(pred_file)
            if ds_pred is None:
                ax.text(0.5, 0.5, "Predicción inválida", ha="center", va="center", transform=ax.transAxes)
                ax.set_title("Predicción inválida")
            else:
                try:
                    z = ds_pred["DSSF_PRED"].values
                    mesh = ax.pcolormesh(ds_pred.lon, ds_pred.lat, z, cmap='Spectral_r', shading='auto', transform=ccrs.PlateCarree(), vmin=100, vmax=1200)
                except Exception:
                    mesh = ax.pcolormesh(ds_pred.lon.values, ds_pred.lat.values, ds_pred.DSSF_PRED.values, cmap='Spectral_r', shading='auto', transform=ccrs.PlateCarree(), vmin=100, vmax=1200)

                for geom in gdf.geometry:
                    polys = [geom] if isinstance(geom, Polygon) else geom.geoms
                    for poly in polys:
                        x, y = poly.exterior.xy
                        ax.plot(x, y, color="black", linewidth=0.6, transform=ccrs.PlateCarree())

                ax.set_title(f"Predicción {time_str_pred}")
                fig.colorbar(mesh, ax=ax, label="GHI (W/m²)", shrink=0.7, pad=0.01)

                try:
                    ds_pred.close()
                except Exception:
                    pass
        else:
            ax.text(0.5, 0.5, "No hay predicción", ha="center", va="center", transform=ax.transAxes)
            ax.set_title("Predicción no disponible")

        plt.tight_layout()
        plt.savefig(ZOOM_PATH, dpi=150, bbox_inches="tight")
        plt.close(fig)
        print(f"{datetime.now()}: Zoom guardado en {ZOOM_PATH}")

    except Exception as e:
        print("Error generando zoom/detalle:", e)


# Programar job cada 15 minutos
scheduler.add_job(job, "interval", minutes=15, next_run_time=datetime.now())

# ---------------------------
# Rutas Flask
# ---------------------------
@app.route("/")
def index():
    has_main = os.path.exists(PLOT_PATH)
    has_zoom = os.path.exists(ZOOM_PATH)

    if has_main:
        zoom_html = f"""
            <h2>Detalle sobre la Provincia de Salta</h2>
            <div class="plot-container">
                <img src="/zoom" alt="Zoom Salta">
            </div>
        """ if has_zoom else "<p>Zoom no disponible aún.</p>"

        html = f"""
        <html>
        <head>
            <title>Monitoreamiento y predicción a muy corto plazo de GHI</title>
            <meta charset="utf-8"/>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    background-color: #f0f2f5;
                    display: flex;
                    flex-direction: column;
                    align-items: center;
                    padding: 20px;
                }}
                h1 {{
                    color: #333;
                    text-align: center;
                    margin-bottom: 20px;
                }}
                .plot-container {{
                    width: 90%;
                    max-width: 1200px;
                    background: white;
                    padding: 20px;
                    border-radius: 15px;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.12);
                    display: flex;
                    justify-content: center;
                    margin-bottom: 24px;
                }}
                img {{
                    width: 100%;
                    height: auto;
                    border-radius: 10px;
                }}
                p {{
                    color: #666;
                    margin-top: 10px;
                    text-align: center;
                }}
                h2 {{
                    color: #333;
                    margin-top: 10px;
                    margin-bottom: 10px;
                }}
            </style>
        </head>
        <body>
            <h1>Monitoreamiento y predicción a muy corto plazo de GHI</h1>
            <div class="plot-container">
                <img src="/plot" alt="Última predicción">
            </div>
            <p>Actualizado automáticamente según disponibilidad de LSA-SAF.</p>

            {zoom_html}

        </body>
        </html>
        """
        return render_template_string(html)
    else:
        return """
        <html>
        <head>
            <title>No hay predicciones</title>
            <meta charset="utf-8"/>
            <style>
                body {{
                    font-family: 'Arial', sans-serif;
                    background-color: #f0f2f5;
                    display: flex;
                    flex-direction: column;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    color: #555;
                }}
                h1 {{
                    font-size: 36px;
                    margin-bottom: 20px;
                }}
            </style>
        </head>
        <body>
            <h1>No hay predicciones aún</h1>
            <p>Cuando se genere la primera predicción, aparecerá aquí.</p>
        </body>
        </html>
        """

@app.route("/plot")
def plot():
    if os.path.exists(PLOT_PATH):
        return send_file(PLOT_PATH, mimetype="image/png")
    else:
        return "No hay imagen aún", 404

@app.route("/zoom")
def zoom():
    if os.path.exists(ZOOM_PATH):
        return send_file(ZOOM_PATH, mimetype="image/png")
    else:
        return "No hay zoom aún", 404



# ---------------------------
# Run Flask
# ---------------------------
if __name__ == "__main__":
    # Ejecuta el job inmediatamente al iniciar (intenta evitar duplicados si scheduler ya lo lanzó)
    try:
        job()
    except Exception as e:
        print("Error ejecutando job inicial:", e)

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
