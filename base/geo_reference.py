"""
Georeferencing helpers for PALMPaint.

This module deliberately keeps all CRS and UTM-related math in one place so the
rest of the application only needs a small, stable API.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Dict, Optional, Tuple

import numpy as np


DEFAULT_ORIGIN_LAT = 52.50965
DEFAULT_ORIGIN_LON = 13.3139
_K0 = 0.9996
_FALSE_EASTING = 500000.0
_FALSE_NORTHING_SOUTH = 10000000.0
_UTM_LAT_MIN = -80.0
_UTM_LAT_MAX = 84.0
_AUTO_GERMANY_EPSGS = {25832, 25833}


@dataclass(frozen=True)
class _Ellipsoid:
    datum_name: str
    geographic_crs_name: str
    ellipsoid_name: str
    semi_major_axis: float
    inverse_flattening: float

    @property
    def flattening(self) -> float:
        return 1.0 / self.inverse_flattening

    @property
    def semi_minor_axis(self) -> float:
        return self.semi_major_axis * (1.0 - self.flattening)

    @property
    def eccentricity_squared(self) -> float:
        f = self.flattening
        return f * (2.0 - f)


_ELLIPSOIDS = {
    "WGS84": _Ellipsoid(
        datum_name="World Geodetic System 1984",
        geographic_crs_name="WGS 84",
        ellipsoid_name="WGS 84",
        semi_major_axis=6378137.0,
        inverse_flattening=298.257223563,
    ),
    "ETRS89": _Ellipsoid(
        datum_name="European Terrestrial Reference System 1989",
        geographic_crs_name="ETRS89",
        ellipsoid_name="GRS 1980",
        semi_major_axis=6378137.0,
        inverse_flattening=298.257222101,
    ),
}


@dataclass(frozen=True)
class GeoReference:
    epsg_code: int
    crs_name: str
    utm_zone: Optional[int]
    hemisphere: Optional[str]
    datum: str
    origin_lat: float
    origin_lon: float
    origin_x: float
    origin_y: float
    rotation_angle: float = 0.0
    crs_wkt: Optional[str] = None
    projected_crs_name: Optional[str] = None

    @property
    def epsg_string(self) -> str:
        return f"EPSG:{self.epsg_code}"

    def as_origin_tuple(self) -> Tuple[float, float, float, float]:
        return (
            float(self.origin_lat),
            float(self.origin_lon),
            float(self.origin_x),
            float(self.origin_y),
        )

    @property
    def auto_conversion_enabled(self) -> bool:
        return self.epsg_code in _AUTO_GERMANY_EPSGS

    @property
    def manual_mode_warning(self) -> str:
        return (
            "Manual mode: automatic conversions are only supported for Germany "
            "(EPSG:25832 / EPSG:25833). You are responsible for the correctness "
            "of the entered coordinates and CRS."
        )


def _as_array(values: Any) -> np.ndarray:
    return np.asarray(values, dtype=np.float64)


def _to_output(values: np.ndarray | np.floating, template: Any) -> Any:
    arr = np.asarray(values)
    if np.isscalar(template):
        return float(arr)
    return arr


def utm_zone_from_lon(lon: float) -> int:
    zone = int(math.floor((float(lon) + 180.0) / 6.0) + 1)
    return min(60, max(1, zone))


def parse_epsg_code(raw_value: Any) -> Optional[int]:
    if raw_value is None:
        return None
    if isinstance(raw_value, (int, np.integer)):
        return int(raw_value)
    if isinstance(raw_value, float) and raw_value.is_integer():
        return int(raw_value)

    text = str(raw_value).strip()
    if not text:
        return None

    match = re.search(r"(\d{4,5})", text)
    if match is None:
        return None
    return int(match.group(1))


def _supported_epsg_from_text(text: str) -> Optional[int]:
    if not text:
        return None
    matches = re.findall(r"(\d{4,5})", text)
    for candidate in reversed(matches):
        epsg_code = int(candidate)
        if is_supported_utm_epsg(epsg_code):
            return epsg_code
    return None


def _supported_epsg_from_name(text: str) -> Optional[int]:
    if not text:
        return None

    zone_match = re.search(r"zone\s+(\d{1,2})\s*([NS])", text, re.IGNORECASE)
    if zone_match is None:
        return None

    zone = int(zone_match.group(1))
    hemisphere = zone_match.group(2).upper()
    upper_text = text.upper()

    if "ETRS89" in upper_text:
        return 25800 + zone
    if "WGS" in upper_text and "84" in upper_text:
        return 32600 + zone if hemisphere == "N" else 32700 + zone
    return None


def detect_dataset_epsg(nc_file: Any) -> Optional[int]:
    if "crs" in nc_file.variables:
        crs_var = nc_file.variables["crs"]
        epsg_code = parse_epsg_code(getattr(crs_var, "epsg_code", None))
        if epsg_code is not None:
            return epsg_code

        for attr_name in ("spatial_ref", "crs_wkt", "projected_crs_name"):
            text = str(getattr(crs_var, attr_name, ""))
            epsg_code = _supported_epsg_from_text(text)
            if epsg_code is not None:
                return epsg_code
            named_epsg = _supported_epsg_from_name(text)
            if named_epsg is not None:
                return named_epsg

    epsg_code = parse_epsg_code(getattr(nc_file, "epsg_code", None))
    if epsg_code is not None:
        return epsg_code

    for attr_name in ("spatial_ref", "crs_wkt", "projected_crs_name"):
        text = str(getattr(nc_file, attr_name, ""))
        epsg_code = _supported_epsg_from_text(text)
        if epsg_code is not None:
            return epsg_code
        named_epsg = _supported_epsg_from_name(text)
        if named_epsg is not None:
            return named_epsg
    return None


def _dataset_crs_name(nc_file: Any) -> Optional[str]:
    if "crs" in nc_file.variables:
        crs_var = nc_file.variables["crs"]
        for attr_name in ("projected_crs_name", "geographic_crs_name", "long_name"):
            value = getattr(crs_var, attr_name, None)
            if value:
                return str(value)
    for attr_name in ("projected_crs_name", "geographic_crs_name", "crs_name"):
        value = getattr(nc_file, attr_name, None)
        if value:
            return str(value)
    return None


def _dataset_crs_wkt(nc_file: Any) -> Optional[str]:
    if "crs" in nc_file.variables:
        crs_var = nc_file.variables["crs"]
        for attr_name in ("crs_wkt", "spatial_ref"):
            value = getattr(crs_var, attr_name, None)
            if value:
                return str(value)
    for attr_name in ("crs_wkt", "spatial_ref"):
        value = getattr(nc_file, attr_name, None)
        if value:
            return str(value)
    return None


def _epsg_params(epsg_code: int) -> Dict[str, Any]:
    if 32601 <= epsg_code <= 32660:
        zone = epsg_code - 32600
        hemisphere = "N"
        ellipsoid_key = "WGS84"
    elif 32701 <= epsg_code <= 32760:
        zone = epsg_code - 32700
        hemisphere = "S"
        ellipsoid_key = "WGS84"
    elif 25828 <= epsg_code <= 25838:
        zone = epsg_code - 25800
        hemisphere = "N"
        ellipsoid_key = "ETRS89"
    else:
        raise ValueError(f"Unsupported EPSG code for direct UTM conversion: {epsg_code}")

    ellipsoid = _ELLIPSOIDS[ellipsoid_key]
    crs_name = f"{ellipsoid.geographic_crs_name} / UTM zone {zone}{hemisphere}"
    return {
        "zone": zone,
        "hemisphere": hemisphere,
        "ellipsoid": ellipsoid,
        "crs_name": crs_name,
    }


def is_supported_utm_epsg(epsg_code: Optional[int]) -> bool:
    if epsg_code is None:
        return False
    try:
        _epsg_params(int(epsg_code))
        return True
    except ValueError:
        return False


def is_auto_conversion_epsg(epsg_code: Optional[int]) -> bool:
    return epsg_code in _AUTO_GERMANY_EPSGS


def suggest_utm_epsg(lat: float, lon: float, prefer_etrs89: bool = True) -> int:
    zone = utm_zone_from_lon(lon)
    hemisphere = "N" if float(lat) >= 0.0 else "S"
    if prefer_etrs89 and hemisphere == "N" and 28 <= zone <= 38:
        return 25800 + zone
    return 32600 + zone if hemisphere == "N" else 32700 + zone


def _looks_like_utm_coordinates(x_value: float, y_value: float) -> bool:
    return 100000.0 <= float(x_value) <= 900000.0 and 0.0 <= float(y_value) <= 10000000.0


def latlon_to_projected(lat: Any, lon: Any, epsg_code: int) -> Tuple[Any, Any]:
    params = _epsg_params(int(epsg_code))
    ellipsoid = params["ellipsoid"]
    lat_arr = _as_array(lat)
    lon_arr = _as_array(lon)

    if np.any(lat_arr < _UTM_LAT_MIN) or np.any(lat_arr > _UTM_LAT_MAX):
        raise ValueError("UTM conversion is only defined for latitudes between -80 and 84 degrees.")

    a = ellipsoid.semi_major_axis
    e2 = ellipsoid.eccentricity_squared
    ep2 = e2 / (1.0 - e2)

    phi = np.deg2rad(lat_arr)
    lam = np.deg2rad(lon_arr)
    lam0 = math.radians(params["zone"] * 6.0 - 183.0)

    sin_phi = np.sin(phi)
    cos_phi = np.cos(phi)
    tan_phi = np.tan(phi)

    n = a / np.sqrt(1.0 - e2 * sin_phi * sin_phi)
    t = tan_phi * tan_phi
    c = ep2 * cos_phi * cos_phi
    a_term = (lam - lam0) * cos_phi

    e4 = e2 * e2
    e6 = e4 * e2
    m = a * (
        (1.0 - e2 / 4.0 - 3.0 * e4 / 64.0 - 5.0 * e6 / 256.0) * phi
        - (3.0 * e2 / 8.0 + 3.0 * e4 / 32.0 + 45.0 * e6 / 1024.0) * np.sin(2.0 * phi)
        + (15.0 * e4 / 256.0 + 45.0 * e6 / 1024.0) * np.sin(4.0 * phi)
        - (35.0 * e6 / 3072.0) * np.sin(6.0 * phi)
    )

    x = _FALSE_EASTING + _K0 * n * (
        a_term
        + (1.0 - t + c) * a_term**3 / 6.0
        + (5.0 - 18.0 * t + t**2 + 72.0 * c - 58.0 * ep2) * a_term**5 / 120.0
    )
    y = _K0 * (
        m
        + n
        * tan_phi
        * (
            a_term**2 / 2.0
            + (5.0 - t + 9.0 * c + 4.0 * c**2) * a_term**4 / 24.0
            + (61.0 - 58.0 * t + t**2 + 600.0 * c - 330.0 * ep2) * a_term**6 / 720.0
        )
    )

    if params["hemisphere"] == "S":
        y = y + _FALSE_NORTHING_SOUTH

    return _to_output(x, lat), _to_output(y, lat)


def projected_to_latlon(x: Any, y: Any, epsg_code: int) -> Tuple[Any, Any]:
    params = _epsg_params(int(epsg_code))
    ellipsoid = params["ellipsoid"]
    x_arr = _as_array(x)
    y_arr = _as_array(y)

    a = ellipsoid.semi_major_axis
    e2 = ellipsoid.eccentricity_squared
    ep2 = e2 / (1.0 - e2)
    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))

    x_rel = x_arr - _FALSE_EASTING
    y_rel = y_arr.copy()
    if params["hemisphere"] == "S":
        y_rel = y_rel - _FALSE_NORTHING_SOUTH

    e4 = e2 * e2
    e6 = e4 * e2
    m = y_rel / _K0
    mu = m / (a * (1.0 - e2 / 4.0 - 3.0 * e4 / 64.0 - 5.0 * e6 / 256.0))

    phi1 = (
        mu
        + (3.0 * e1 / 2.0 - 27.0 * e1**3 / 32.0) * np.sin(2.0 * mu)
        + (21.0 * e1**2 / 16.0 - 55.0 * e1**4 / 32.0) * np.sin(4.0 * mu)
        + (151.0 * e1**3 / 96.0) * np.sin(6.0 * mu)
        + (1097.0 * e1**4 / 512.0) * np.sin(8.0 * mu)
    )

    sin_phi1 = np.sin(phi1)
    cos_phi1 = np.cos(phi1)
    tan_phi1 = np.tan(phi1)
    n1 = a / np.sqrt(1.0 - e2 * sin_phi1 * sin_phi1)
    r1 = a * (1.0 - e2) / np.power(1.0 - e2 * sin_phi1 * sin_phi1, 1.5)
    t1 = tan_phi1 * tan_phi1
    c1 = ep2 * cos_phi1 * cos_phi1
    d = x_rel / (n1 * _K0)

    lat_rad = phi1 - (n1 * tan_phi1 / r1) * (
        d**2 / 2.0
        - (5.0 + 3.0 * t1 + 10.0 * c1 - 4.0 * c1**2 - 9.0 * ep2) * d**4 / 24.0
        + (61.0 + 90.0 * t1 + 298.0 * c1 + 45.0 * t1**2 - 252.0 * ep2 - 3.0 * c1**2)
        * d**6
        / 720.0
    )

    lon0 = math.radians(params["zone"] * 6.0 - 183.0)
    lon_rad = lon0 + (
        d
        - (1.0 + 2.0 * t1 + c1) * d**3 / 6.0
        + (5.0 - 2.0 * c1 + 28.0 * t1 - 3.0 * c1**2 + 8.0 * ep2 + 24.0 * t1**2)
        * d**5
        / 120.0
    ) / cos_phi1

    lat_deg = np.rad2deg(lat_rad)
    lon_deg = np.rad2deg(lon_rad)
    return _to_output(lon_deg, x), _to_output(lat_deg, x)


def georeference_from_latlon(
    lat: float,
    lon: float,
    epsg_code: Optional[int] = None,
    rotation_angle: float = 0.0,
    prefer_etrs89: bool = True,
) -> GeoReference:
    selected_epsg = int(epsg_code or suggest_utm_epsg(lat, lon, prefer_etrs89=prefer_etrs89))
    origin_x, origin_y = latlon_to_projected(lat, lon, selected_epsg)
    params = _epsg_params(selected_epsg)
    return GeoReference(
        epsg_code=selected_epsg,
        crs_name=params["crs_name"],
        utm_zone=params["zone"],
        hemisphere=params["hemisphere"],
        datum=params["ellipsoid"].datum_name,
        origin_lat=float(lat),
        origin_lon=float(lon),
        origin_x=float(origin_x),
        origin_y=float(origin_y),
        rotation_angle=float(rotation_angle),
        projected_crs_name=params["crs_name"],
    )


def georeference_from_projected(
    x: float,
    y: float,
    epsg_code: int,
    rotation_angle: float = 0.0,
) -> GeoReference:
    lon, lat = projected_to_latlon(x, y, epsg_code)
    params = _epsg_params(int(epsg_code))
    return GeoReference(
        epsg_code=int(epsg_code),
        crs_name=params["crs_name"],
        utm_zone=params["zone"],
        hemisphere=params["hemisphere"],
        datum=params["ellipsoid"].datum_name,
        origin_lat=float(lat),
        origin_lon=float(lon),
        origin_x=float(x),
        origin_y=float(y),
        rotation_angle=float(rotation_angle),
        projected_crs_name=params["crs_name"],
    )


def manual_georeference(
    origin_lat: float,
    origin_lon: float,
    origin_x: float,
    origin_y: float,
    epsg_code: int,
    rotation_angle: float = 0.0,
    crs_name: Optional[str] = None,
    crs_wkt: Optional[str] = None,
) -> GeoReference:
    display_name = crs_name or f"Manual CRS ({int(epsg_code)})"
    return GeoReference(
        epsg_code=int(epsg_code),
        crs_name=display_name,
        utm_zone=None,
        hemisphere=None,
        datum="manual",
        origin_lat=float(origin_lat),
        origin_lon=float(origin_lon),
        origin_x=float(origin_x),
        origin_y=float(origin_y),
        rotation_angle=float(rotation_angle),
        crs_wkt=crs_wkt,
        projected_crs_name=display_name,
    )


def complete_georeference(
    origin_lat: Optional[float] = None,
    origin_lon: Optional[float] = None,
    origin_x: Optional[float] = None,
    origin_y: Optional[float] = None,
    epsg_code: Optional[int] = None,
    rotation_angle: float = 0.0,
    prefer_projected: bool = False,
    prefer_etrs89: bool = True,
    allow_manual: bool = False,
    crs_name: Optional[str] = None,
    crs_wkt: Optional[str] = None,
) -> GeoReference:
    if epsg_code is None:
        if origin_lat is not None and origin_lon is not None:
            epsg_code = suggest_utm_epsg(origin_lat, origin_lon, prefer_etrs89=prefer_etrs89)
        else:
            raise ValueError("An EPSG code is required when only projected coordinates are given.")

    selected_epsg = int(epsg_code)
    has_latlon = origin_lat is not None and origin_lon is not None
    has_projected = origin_x is not None and origin_y is not None

    if not is_auto_conversion_epsg(selected_epsg):
        if allow_manual and has_latlon and has_projected:
            return manual_georeference(
                origin_lat=origin_lat,
                origin_lon=origin_lon,
                origin_x=origin_x,
                origin_y=origin_y,
                epsg_code=selected_epsg,
                rotation_angle=rotation_angle,
                crs_name=crs_name,
                crs_wkt=crs_wkt,
            )
        raise ValueError(
            "Automatic conversions are only supported for Germany "
            "(EPSG:25832 / EPSG:25833). Enter all coordinates manually."
        )

    if has_latlon and has_projected:
        if prefer_projected:
            return georeference_from_projected(origin_x, origin_y, selected_epsg, rotation_angle)
        return georeference_from_latlon(origin_lat, origin_lon, selected_epsg, rotation_angle)
    if has_latlon:
        return georeference_from_latlon(origin_lat, origin_lon, selected_epsg, rotation_angle)
    if has_projected:
        return georeference_from_projected(origin_x, origin_y, selected_epsg, rotation_angle)
    raise ValueError("A complete set of origin coordinates is required.")


def default_georeference() -> GeoReference:
    return georeference_from_latlon(DEFAULT_ORIGIN_LAT, DEFAULT_ORIGIN_LON)


def snap_georeference_to_grid(georef: GeoReference, grid_resolution: float) -> GeoReference:
    """Snap projected origin coordinates to the grid and recompute lat/lon consistently."""
    step = float(grid_resolution)
    if step <= 0.0 or not georef.auto_conversion_enabled:
        return georef

    snapped_x = round(georef.origin_x / step) * step
    snapped_y = round(georef.origin_y / step) * step
    return georeference_from_projected(
        snapped_x,
        snapped_y,
        georef.epsg_code,
        rotation_angle=georef.rotation_angle,
    )


def ensure_georeference(
    origin: Optional[Tuple[float, float, float, float]] = None,
    georef: Optional[GeoReference] = None,
    epsg_code: Optional[int] = None,
    rotation_angle: float = 0.0,
) -> GeoReference:
    if georef is not None:
        return georef
    if origin is None:
        return default_georeference()

    origin_lat, origin_lon, origin_x, origin_y = origin
    inferred_epsg = epsg_code or suggest_utm_epsg(origin_lat, origin_lon)
    prefer_projected = _looks_like_utm_coordinates(origin_x, origin_y)
    return complete_georeference(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        origin_x=origin_x,
        origin_y=origin_y,
        epsg_code=inferred_epsg,
        rotation_angle=rotation_angle,
        prefer_projected=prefer_projected,
        allow_manual=True,
    )


def load_georeference(nc_file: Any) -> GeoReference:
    origin_lat = getattr(nc_file, "origin_lat", None)
    origin_lon = getattr(nc_file, "origin_lon", None)
    origin_x = getattr(nc_file, "origin_x", None)
    origin_y = getattr(nc_file, "origin_y", None)
    rotation_angle = float(getattr(nc_file, "rotation_angle", 0.0))

    epsg_code = detect_dataset_epsg(nc_file)
    crs_name = _dataset_crs_name(nc_file)
    crs_wkt = _dataset_crs_wkt(nc_file)
    if epsg_code is None and origin_lat is not None and origin_lon is not None:
        epsg_code = suggest_utm_epsg(origin_lat, origin_lon)

    if origin_lat is None and origin_lon is None and origin_x is None and origin_y is None:
        return default_georeference()

    prefer_projected = bool(
        epsg_code is not None
        and origin_x is not None
        and origin_y is not None
        and _looks_like_utm_coordinates(origin_x, origin_y)
    )

    return complete_georeference(
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        origin_x=origin_x,
        origin_y=origin_y,
        epsg_code=epsg_code,
        rotation_angle=rotation_angle,
        prefer_projected=prefer_projected,
        allow_manual=True,
        crs_name=crs_name,
        crs_wkt=crs_wkt,
    )


def generate_coordinate_fields(
    nx: int,
    ny: int,
    res: float,
    georef: GeoReference,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    if not georef.auto_conversion_enabled:
        raise ValueError("2-D coordinate fields can only be generated for automatic Germany UTM mode.")

    x_local = np.arange(0.0, nx * res, res, dtype=np.float64) + 0.5 * res
    y_local = np.arange(0.0, ny * res, res, dtype=np.float64) + 0.5 * res

    e_utm = georef.origin_x + x_local[np.newaxis, :]
    n_utm = georef.origin_y + y_local[:, np.newaxis]
    e_utm = np.broadcast_to(e_utm, (ny, nx)).copy()
    n_utm = np.broadcast_to(n_utm, (ny, nx)).copy()

    lon, lat = projected_to_latlon(e_utm, n_utm, georef.epsg_code)
    return (
        e_utm.astype(np.float32),
        n_utm.astype(np.float32),
        np.asarray(lat, dtype=np.float32),
        np.asarray(lon, dtype=np.float32),
    )


def _crs_variable_attributes(georef: GeoReference) -> Dict[str, Any]:
    if not georef.auto_conversion_enabled:
        attrs = {
            "long_name": "coordinate reference system",
            "projected_crs_name": georef.projected_crs_name or georef.crs_name,
            "epsg_code": georef.epsg_string,
            "units": "m",
        }
        if georef.crs_wkt:
            attrs["crs_wkt"] = georef.crs_wkt
        return attrs

    params = _epsg_params(georef.epsg_code)
    ellipsoid = params["ellipsoid"]
    central_meridian = georef.utm_zone * 6.0 - 183.0
    false_northing = 0.0 if georef.hemisphere == "N" else _FALSE_NORTHING_SOUTH

    crs_wkt = (
        f'PROJCRS["{georef.crs_name}",'
        f'BASEGEOGCRS["{ellipsoid.geographic_crs_name}",'
        f'DATUM["{ellipsoid.datum_name}",'
        f'ELLIPSOID["{ellipsoid.ellipsoid_name}",{ellipsoid.semi_major_axis},'
        f'{ellipsoid.inverse_flattening},LENGTHUNIT["metre",1]]],'
        'PRIMEM["Greenwich",0,ANGLEUNIT["degree",0.0174532925199433]]],'
        f'CONVERSION["UTM zone {georef.utm_zone}{georef.hemisphere}",'
        'METHOD["Transverse Mercator",ID["EPSG",9807]],'
        'PARAMETER["Latitude of natural origin",0,ANGLEUNIT["degree",0.0174532925199433],'
        'ID["EPSG",8801]],'
        f'PARAMETER["Longitude of natural origin",{central_meridian},'
        'ANGLEUNIT["degree",0.0174532925199433],ID["EPSG",8802]],'
        'PARAMETER["Scale factor at natural origin",0.9996,SCALEUNIT["unity",1],'
        'ID["EPSG",8805]],'
        'PARAMETER["False easting",500000,LENGTHUNIT["metre",1],ID["EPSG",8806]],'
        f'PARAMETER["False northing",{false_northing},LENGTHUNIT["metre",1],ID["EPSG",8807]]],'
        'CS[Cartesian,2],'
        'AXIS["easting",east,ORDER[1],LENGTHUNIT["metre",1]],'
        'AXIS["northing",north,ORDER[2],LENGTHUNIT["metre",1]],'
        f'ID["EPSG",{georef.epsg_code}]]'
    )

    return {
        "long_name": "coordinate reference system",
        "crs_wkt": crs_wkt,
        "semi_major_axis": ellipsoid.semi_major_axis,
        "semi_minor_axis": ellipsoid.semi_minor_axis,
        "inverse_flattening": ellipsoid.inverse_flattening,
        "reference_ellipsoid_name": ellipsoid.ellipsoid_name,
        "longitude_of_prime_meridian": 0.0,
        "prime_meridian_name": "Greenwich",
        "geographic_crs_name": ellipsoid.geographic_crs_name,
        "horizontal_datum_name": ellipsoid.datum_name,
        "projected_crs_name": georef.crs_name,
        "grid_mapping_name": "transverse_mercator",
        "latitude_of_projection_origin": 0.0,
        "longitude_of_central_meridian": central_meridian,
        "false_easting": _FALSE_EASTING,
        "false_northing": false_northing,
        "scale_factor_at_central_meridian": _K0,
        "epsg_code": georef.epsg_string,
        "units": "m",
    }


def add_grid_mapping(variable: Any, coordinates: str = "E_UTM N_UTM lon lat") -> None:
    if coordinates:
        variable.coordinates = coordinates
    variable.grid_mapping = "crs"


def coordinate_attribute_names(georef: GeoReference) -> Optional[str]:
    if georef.auto_conversion_enabled:
        return "E_UTM N_UTM lon lat"
    return None


def write_georeference(nc_file: Any, nx: int, ny: int, res: float, georef: GeoReference) -> None:
    if georef.auto_conversion_enabled:
        e_utm, n_utm, lat, lon = generate_coordinate_fields(nx, ny, res, georef)

        lat_var = nc_file.createVariable("lat", "f4", ("y", "x"), fill_value=-9999.0)
        lat_var.long_name = "latitude"
        lat_var.units = "degrees_north"
        lat_var.standard_name = "latitude"
        lat_var[:, :] = lat

        lon_var = nc_file.createVariable("lon", "f4", ("y", "x"), fill_value=-9999.0)
        lon_var.long_name = "longitude"
        lon_var.units = "degrees_east"
        lon_var.standard_name = "longitude"
        lon_var[:, :] = lon

        e_var = nc_file.createVariable("E_UTM", "f4", ("y", "x"), fill_value=-9999.0)
        e_var.units = "m"
        e_var.long_name = "easting"
        e_var.standard_name = "projection_x_coordinate"
        e_var[:, :] = e_utm

        n_var = nc_file.createVariable("N_UTM", "f4", ("y", "x"), fill_value=-9999.0)
        n_var.units = "m"
        n_var.long_name = "northing"
        n_var.standard_name = "projection_y_coordinate"
        n_var[:, :] = n_utm

    crs = nc_file.createVariable("crs", "i4")
    for attr_name, attr_value in _crs_variable_attributes(georef).items():
        setattr(crs, attr_name, attr_value)

    nc_file.origin_lat = georef.origin_lat
    nc_file.origin_lon = georef.origin_lon
    nc_file.origin_x = georef.origin_x
    nc_file.origin_y = georef.origin_y
    nc_file.origin_z = 0.0
    nc_file.rotation_angle = georef.rotation_angle
