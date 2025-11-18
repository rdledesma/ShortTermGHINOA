# settings.py
import os

# URL base MLST en NetCDF
BASE_URL = "https://datalsasaf.lsasvcs.ipma.pt/PRODUCTS/MSG/MLST/NETCDF"

# Credenciales
USERNAME = os.getenv("LSA_USER", "rdledesma")
PASSWORD = os.getenv("LSA_PASS", "Dario449997+")

# Carpeta donde se guardan los archivos
DOWNLOAD_DIR = "crops"

# Dominio espacial a recortar
LAT_MIN = -30.0
LAT_MAX = -20.0
LON_MIN = -70.0
LON_MAX = -60.0
