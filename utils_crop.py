import xarray as xr
import numpy as np


def drop_encoding(ds: xr.Dataset):
    """
    Limpia el encoding de cada variable del dataset.
    Compatible con todas las versiones de xarray.
    """
    for var in ds.variables:
        # Algunos objetos tienen .encoding, otros no
        try:
            ds[var].encoding = {}
        except Exception:
            pass
    return ds


def interpolate_nans(ds: xr.Dataset, varname: str):
    """
    Interpola NaNs en una variable 2D o 3D de xarray usando método linear.
    """
    da = ds[varname]

    # Si tiene dimensiones (time, lat, lon)
    if "time" in da.dims:
        da_interp = da.interpolate_na(
            dim="lat", method="linear", fill_value="extrapolate"
        ).interpolate_na(
            dim="lon", method="linear", fill_value="extrapolate"
        )
    else:
        # si solo es (lat, lon)
        da_interp = da.interpolate_na(
            dim="lat", method="linear", fill_value="extrapolate"
        ).interpolate_na(
            dim="lon", method="linear", fill_value="extrapolate"
        )

    ds[varname] = da_interp
    return ds


def crop_domain(ds, lat_min, lat_max, lon_min, lon_max):
    """
    Recorta el dataset al dominio especificado.
    Nota: en LSA-SAF, la latitud decrece (N->S).
    """
    return ds.sel(
        lat=slice(lat_max, lat_min),
        lon=slice(lon_min, lon_max)
    )
