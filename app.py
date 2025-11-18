# app.py
from flask import Flask, send_file, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import os
from datetime import datetime
import matplotlib.pyplot as plt
import xarray as xr
import cartopy.crs as ccrs
import cartopy.feature as cfeature
from downloader import download_latest_netcdf, clean_old_files
from Prediction import run_prediction
import glob
import pandas as pd
import numpy as np
app = Flask(__name__)
DOWNLOAD_DIR = 'crops'
PLOT_PATH = "static/last_prediction.png"
# ---------------------------
# Scheduler para correr cada 15 minutos
# ---------------------------
scheduler = BackgroundScheduler()


from datetime import timedelta
import cartopy.crs as ccrs
import cartopy.feature as cfeature

from datetime import timedelta
import cartopy.crs as ccrs
import cartopy.feature as cfeature

def job():
    print(f"{datetime.now()}: Ejecutando descarga y predicción...")

    # --- Paso 1: asegurar carpeta ---
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)

    # --- Paso 2: descargar últimos netCDF ---
    try:
        files = download_latest_netcdf()
        clean_old_files()
    except Exception as e:
        print("Error descargando archivos:", e)
        files = []

    # Solo continuar si tenemos al menos 4 archivos
    if len(files) < 4:
        print("No hay suficientes archivos descargados. Usando los últimos disponibles en crops/")
        files = sorted(glob.glob(os.path.join(DOWNLOAD_DIR, "*.nc")))[-4:]

    if len(files) == 0:
        print("No hay archivos netCDF disponibles. Abortando job.")
        return

    # --- Paso 3: generar predicción ---
    try:
        pred_file = run_prediction()  # ya devuelve nombre del netCDF generado
    except Exception as e:
        print("Error generando predicción:", e)
        pred_file = None

    # --- Paso 4: plot de inputs + predicción ---
    # --- Paso 4: plot de inputs + predicción ---
    try:
        fig, axes = plt.subplots(1, 5, figsize=(20,6), subplot_kw={'projection': ccrs.PlateCarree()})
        
        lon_min, lon_max = -70, -60
        lat_min, lat_max = -30, -20

        # Provincias de Argentina
        provincias = cfeature.NaturalEarthFeature(
            category='cultural',
            name='admin_1_states_provinces_lines',  # <--- Límites de provincias
            scale='10m',
            facecolor='none'
        )

        for i, fpath in enumerate(files):
            ds = xr.open_dataset(fpath)
            time_input = ds.time.values[0]
            time_adjusted = pd.to_datetime(time_input) - pd.Timedelta(minutes=180)
            time_str = time_adjusted.strftime("%H:%M %d %b %Y")

            data = ds["DSSF_TOT"].isel(time=0)

            ax = axes[i]
            ax.set_extent([lon_min, lon_max, lat_min, lat_max])
            ax.add_feature(cfeature.LAND, facecolor='lightgray')
            ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
            ax.add_feature(cfeature.BORDERS, linewidth=1)
            ax.add_feature(provincias, edgecolor='black', linewidth=1)
            im = ax.pcolormesh(ds.lon, ds.lat, data, cmap="Oranges", shading="auto")
            ax.set_title(f"{time_str}")
            fig.colorbar(im, ax=ax, orientation='vertical', fraction=0.046)

        # Predicción
        if pred_file and os.path.exists(pred_file):
            ds_pred = xr.open_dataset(pred_file)
            time_pred = pd.to_datetime(ds_pred.coords['time'].values) + pd.Timedelta(minutes=15 - 180)
            time_str = time_pred.strftime("%H:%M %d %b %Y")

            ax = axes[4]
            ax.set_extent([lon_min, lon_max, lat_min, lat_max])
            ax.add_feature(cfeature.LAND, facecolor='lightgray')
            ax.add_feature(cfeature.COASTLINE, linewidth=0.8)
            ax.add_feature(cfeature.BORDERS, linewidth=1)
            ax.add_feature(provincias, edgecolor='black', linewidth=1)
            im = ax.pcolormesh(ds_pred.lon, ds_pred.lat, ds_pred.DSSF_PRED.values, cmap="Oranges", shading="auto")
            ax.set_title(f"Predicción {time_str}")
            fig.colorbar(im, ax=ax, orientation='vertical', fraction=0.046)
        else:
            ax = axes[4]
            ax.text(0.5, 0.5, "No predicción", ha="center", va="center", transform=ax.transAxes)
            ax.set_title("Predicción")

        plt.tight_layout()
        plt.savefig(PLOT_PATH)
        plt.close(fig)
        print(f"{datetime.now()}: Plot actualizado en {PLOT_PATH}")
    except Exception as e:
        print("Error generando plot:", e)







scheduler.add_job(job, "interval", minutes=15)
scheduler.start()

# ---------------------------
# Rutas Flask
# ---------------------------
@app.route("/")
def index():
    if os.path.exists(PLOT_PATH):
        html = f"""
        <html>
        <head>
            <title>Monitoreamiento y predicción a muy corto plazo de GHI </title>
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
                    margin-bottom: 40px;
                }}
                .plot-container {{
                    width: 90%;
                    max-width: 1200px;
                    background: white;
                    padding: 20px;
                    border-radius: 15px;
                    box-shadow: 0 8px 20px rgba(0,0,0,0.2);
                    display: flex;
                    justify-content: center;
                }}
                img {{
                    width: 100%;
                    height: auto;
                    border-radius: 10px;
                }}
                p {{
                    color: #666;
                    margin-top: 20px;
                    text-align: center;
                }}
            </style>
        </head>
        <body>
            <h1>Monitoreamiento y predicción a muy corto plazo de GHI</h1>
            <div class="plot-container">
                <img src="/plot">
            </div>
            <p>Actualizado automáticamente según disponibilidad de LSA-SAF.</p>
        </body>
        </html>
        """
        return render_template_string(html)
    else:
        return """
        <html>
        <head>
            <title>No hay predicciones</title>
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

# ---------------------------
# Run Flask
# ---------------------------
if __name__ == "__main__":
    # Ejecuta el job inmediatamente al iniciar
    job()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
