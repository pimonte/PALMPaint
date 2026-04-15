BUILDING_CONFIG = {
    "default_type": 2,
    "types": {
        1: {"label": "Residential, built before 1950", "display": {"color": "#761002"}},
        2: {"label": "Residential, built from 1950-2000", "display": {"color": "#8f1402"}},
        3: {"label": "Residential, built after 2000", "display": {"color": "#a81802"}},
        4: {"label": "Non-residential, built before 1950", "display": {"color": "#1f262e"}},
        5: {"label": "Non-residential, built from 1950-2000", "display": {"color": "#29333d"}},
        6: {"label": "Non-residential, built after 2000", "display": {"color": "#343f4c"}},
    },
    "parameter_dimensions": {
        "building_general_par": 2,
        "building_indoor_par": 19,
        "building_surface_layer": 4,
        "building_surface_level": 3,
        "building_surface_type": 9,
        "nbuilding_surface_pars": 19,
    },
    "parameter_specs": (
        ("building_albedo_type", ("building_surface_type",)),
        ("building_emissivity", ("building_surface_type",)),
        ("building_fraction", ("building_surface_type",)),
        ("building_general_pars", ("building_general_par",)),
        ("building_heat_capacity", ("building_surface_type", "building_surface_layer")),
        ("building_heat_conductivity", ("building_surface_type", "building_surface_layer")),
        ("building_indoor_pars", ("building_indoor_par",)),
        ("building_lai", ("building_surface_level",)),
        ("building_roughness_length", ("building_surface_level",)),
        ("building_roughness_length_qh", ("building_surface_level",)),
        ("building_thickness", ("building_surface_type", "building_surface_layer")),
        ("building_transmissivity", ("building_surface_level",)),
    ),
    "parameter_metadata": {
        "building_albedo_type": {"long_name": "x-y specific setting of building albedo type", "units": "1"},
        "building_emissivity": {"long_name": "x-y specific setting of building emissivity", "units": "1"},
        "building_fraction": {"long_name": "x-y specific setting of building fractions", "units": "1"},
        "building_general_pars": {"long_name": "x-y specific setting of general building parameters", "units": "see building_general_par"},
        "building_heat_capacity": {"long_name": "x-y specific setting of heat capacity of building surfaces", "units": "J m-3 K-1"},
        "building_heat_conductivity": {"long_name": "x-y specific setting of thermal conductivity of building surfaces", "units": "W m-1 K-1"},
        "building_indoor_pars": {"long_name": "x-y specific setting of building indoor parameters", "units": "see building_indoor_par"},
        "building_lai": {"long_name": "x-y specific setting of leaf-area index at green fraction of building surfaces", "units": "m2 m-2"},
        "building_roughness_length": {"long_name": "x-y specific setting of roughness length for momentum at building surfaces", "units": "m"},
        "building_roughness_length_qh": {"long_name": "x-y specific setting of roughness length for heat and moisture at building surfaces", "units": "m"},
        "building_thickness": {"long_name": "x-y specific setting of building wall-layer thicknesses", "units": "m"},
        "building_transmissivity": {"long_name": "x-y specific setting of transmissivity of windows at building surfaces", "units": "1"},
    },
}


def default_building_type():
    return int(BUILDING_CONFIG.get("default_type", 1))
