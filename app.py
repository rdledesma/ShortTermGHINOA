# app.py
from flask import Flask, send_file, render_template_string
from apscheduler.schedulers.background import BackgroundScheduler
import os
from datetime import datetime
import matplotlib.pyplot as plt
import xarray as xr
import numpy as np
from downloader import download_latest_netcdf, clean_old_files
from Prediction import run_prediction

app = Flask(__name__)

PLOT_PATH = "static/last_prediction.png"
DOWNLOAD_DIR = "crops"

# ---------------------------
# Scheduler para correr cada 15 minutos
# ---------------------------
scheduler = BackgroundScheduler()

def job():
    print(f"{datetime.now()}: Ejecutando descarga y predicción...")
    files = download_latest_netcdf()
    clean_old_files()
    if files:
        run_prediction(files)  # tu función ya genera NetCDF y guarda resultados
        # Generar plot con las 4 imágenes descargadas + predicción
        fig, axes = plt.subplots(1, 5, figsize=(20,4))
        for i, fpath in enumerate(files):
            ds = xr.open_dataset(fpath)
            ds["DSSF_TOT"].isel(time=0).plot(ax=axes[i], cmap="viridis")
            axes[i].set_title(f"Input {i+1}")
        # Predicción
        pred_file = "prediccion_DSSF_latest.nc"
        if os.path.exists(pred_file):
            ds_pred = xr.open_dataset(pred_file)
            ds_pred["DSSF_TOT"].isel(time=0).plot(ax=axes[4], cmap="viridis")
            axes[4].set_title("Predicción")
        plt.tight_layout()
        plt.savefig(PLOT_PATH)
        plt.close(fig)
        print(f"{datetime.now()}: Plot actualizado en {PLOT_PATH}")

scheduler.add_job(job, "interval", minutes=15)
scheduler.start()

# ---------------------------
# Rutas Flask
# ---------------------------
@app.route("/")
def index():
    if os.path.exists(PLOT_PATH):
        html = f"""
        <h1>Última predicción LSA-SAF</h1>
        <img src="/plot" width="100%">
        """
        return render_template_string(html)
    else:
        return "<h1>No hay predicciones aún</h1>"

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
    # Ejecuta primero el job para tener algo al iniciar
    job()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))



# # app.py
# from flask import Flask, send_file, render_template_string
# import os

# app = Flask(__name__)

# # Ruta de la imagen de prueba
# PLOT_PATH = "static/last_prediction.png"

# @app.route("/")
# def index():
#     if os.path.exists(PLOT_PATH):
#         html = f"""
#         <h1>Última predicción LSA-SAF (Prueba)</h1>
#         <img src="/plot" width="100%">
#         """
#         return render_template_string(html)
#     else:
#         return "<h1>No hay imagen aún</h1>"

# @app.route("/plot")
# def plot():
#     if os.path.exists(PLOT_PATH):
#         return send_file(PLOT_PATH, mimetype="image/png")
#     else:
#         return "No hay imagen aún", 404

# if __name__ == "__main__":
#     # Flask escucha en el puerto asignado por Render
#     port = int(os.environ.get("PORT", 5000))
#     app.run(host="0.0.0.0", port=port)
