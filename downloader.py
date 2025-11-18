# downloader.py
import os
import re
import requests
from datetime import datetime, timedelta, UTC
from requests.auth import HTTPBasicAuth
import xarray as xr
import glob

from settings import BASE_URL, USERNAME, PASSWORD, DOWNLOAD_DIR
from settings import LAT_MIN, LAT_MAX, LON_MIN, LON_MAX
from utils_crop import crop_domain


def ensure_dir():
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)


def get_available_files(year, month, day):
    """
    Devuelve lista de archivos .nc disponibles en YYYY/MM/DD.
    """
    url = f"{BASE_URL}/{year}/{month:02d}/{day:02d}/"
    print("Consultando:", url)

    r = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD))

    if r.status_code != 200:
        return []

    # Buscar archivos .nc
    files = re.findall(r'>([^<]+\.nc)<', r.text)
    return sorted(files)


def get_latest_available_files():
    """
    Retrocede hora por hora hasta encontrar el día donde existen archivos MLST.
    """
    now_utc = datetime.now(UTC)

    for i in range(12):  # retrocede hasta 12 horas
        ref = now_utc - timedelta(hours=i)
        y, m, d = ref.year, ref.month, ref.day

        files = get_available_files(y, m, d)
        if files:
            print(f"Archivos encontrados en {y}-{m:02d}-{d:02d}")
            return y, m, d, files

    print("No se encontraron archivos recientes en las últimas 12 horas.")
    return None, None, None, []


def download_and_crop_file(remote_fname, year, month, day, max_retries=3):
    """
    Descarga un archivo NetCDF verificando tamaño y lo recorta al dominio.
    Reintenta si el archivo descargado es incompleto.
    """

    url = f"{BASE_URL}/{year}/{month:02d}/{day:02d}/{remote_fname}"
    local_path = os.path.join(DOWNLOAD_DIR, remote_fname)
    tmp_path = os.path.join(DOWNLOAD_DIR, f"tmp_{remote_fname}")

    # --- Paso 1: obtener tamaño real del archivo remoto ---
    head = requests.head(url, auth=HTTPBasicAuth(USERNAME, PASSWORD))
    if "Content-Length" in head.headers:
        remote_size = int(head.headers["Content-Length"])
    else:
        print(f"No se pudo verificar tamaño remoto de {remote_fname}")
        remote_size = None

    for attempt in range(1, max_retries + 1):

        print(f"Descargando ({attempt}/{max_retries}):", url)

        r = requests.get(url, auth=HTTPBasicAuth(USERNAME, PASSWORD), stream=True)

        if r.status_code != 200:
            print("Error HTTP:", r.status_code)
            return None

        with open(tmp_path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)

        # --- Paso 2: validar tamaño ---
        local_size = os.path.getsize(tmp_path)

        if remote_size is not None and local_size != remote_size:
            print(f"Archivo incompleto ({local_size} / {remote_size}). Reintentando...")
            os.remove(tmp_path)
            continue

        # --- Paso 3: intentar abrir con xarray ---
        try:
            with xr.open_dataset(tmp_path) as ds:
                ds_crop = crop_domain(ds, LAT_MIN, LAT_MAX, LON_MIN, LON_MAX)
                ds_crop.to_netcdf(local_path)
            print("Archivo recortado OK:", remote_fname)
            os.remove(tmp_path)
            return local_path

        except Exception as e:
            print("Error leyendo NetCDF:", e)
            print("El archivo parece corrupto. Reintentando...")
            os.remove(tmp_path)

    print(f"FALLÓ LA DESCARGA DE {remote_fname} DESPUÉS DE {max_retries} INTENTOS")
    return None


def download_latest_netcdf(n_last=4):
    """
    Descarga y recorta los últimos N archivos MLST disponibles.
    """

    ensure_dir()

    year, month, day, files = get_latest_available_files()

    if not files:
        print("No hay archivos disponibles para descargar.")
        return []

    last_files = files[-n_last:]

    local_paths = []
    for fname in last_files:
        p = download_and_crop_file(fname, year, month, day)
        if p:
            local_paths.append(p)

    return local_paths


def clean_old_files(n_keep=4):
    """
    Mantiene solo los últimos n_keep archivos y borra el resto.
    """
    all_files = sorted(glob.glob(os.path.join(DOWNLOAD_DIR, "*.nc")))
    excess = all_files[:-n_keep]

    for f in excess:
        os.remove(f)
        print("Eliminado:", f)


if __name__ == "__main__":

    print("\n--- DESCARGANDO LSA-SAF MLST ---\n")

    paths = download_latest_netcdf(n_last=4)

    print("\nDescargados y recortados:")
    for p in paths:
        print(" →", p)

    clean_old_files()

    print("\nSolo quedan los últimos 4 archivos.\n")
