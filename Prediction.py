import glob
import os
from datetime import datetime

import numpy as np
import xarray as xr
import joblib
import tensorflow as tf

from utils_crop import drop_encoding, interpolate_nans


MODEL_PATH = "convLSTM_many2one.keras"
SCALER_X_PATH = "scaler_X.joblib"
SCALER_Y_PATH = "scaler_Y.joblib"

OUTPUT_DIR = "outputs"
if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)


def build_arrays(files):
    ds = xr.open_mfdataset(
        files,
        combine="by_coords",
        preprocess=drop_encoding,
        engine="h5netcdf"
    )

    ds = ds.sortby("lat")
    ds = interpolate_nans(ds, "DSSF_TOT")

    arr = ds["DSSF_TOT"].values     # (4, lat, lon)
    arr = np.expand_dims(arr, axis=-1)
    arr = arr.astype(np.float32)

    return arr, ds


def run_prediction():
    print("Cargando modelo...")
    model = tf.keras.models.load_model(MODEL_PATH)

    print("Cargando scalers...")
    scaler_X = joblib.load(SCALER_X_PATH)
    scaler_Y = joblib.load(SCALER_Y_PATH)

    # Buscar las últimas 4 imágenes
    files = sorted(glob.glob("crops/*.nc"))[-4:]
    print("Usando archivos:")
    for f in files:
        print(" -", f)

    if len(files) < 4:
        print("Error: no hay suficientes imágenes para predecir.")
        return None

    # Construcción del batch
    X, ds_ref = build_arrays(files)

    # Escalar entrada
    X_scaled = scaler_X.transform(X.reshape(-1, 1)).reshape(X.shape)
    X_scaled = np.expand_dims(X_scaled, axis=0)  # (1,4,h,w,1)

    # Predicción
    pred_scaled = model.predict(X_scaled)[0]

    # Desescalado
    pred = scaler_Y.inverse_transform(pred_scaled.reshape(-1, 1)).reshape(pred_scaled.shape)

    # Preparar nombre output
    timestamp = ds_ref.time.values[-1]
    stamp = str(timestamp).replace(":", "").replace(" ", "_")

    outfile = f"prediccion_DSSF_latest.nc"

    # Guardar netCDF
    xr.Dataset(
        {
            "DSSF_PRED": (("lat", "lon"), pred[:, :, 0])
        },
        coords={
            "lat": ds_ref.lat,
            "lon": ds_ref.lon,
            "time": timestamp
        }
    ).to_netcdf(outfile)

    print("Archivo generado:", os.path.basename(outfile))
    return outfile


# NO ejecutar nada automáticamente
# Sin código debajo de esto
