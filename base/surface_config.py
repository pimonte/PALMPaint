SURFACE_CONFIG = {
    "vegetation": {
        "default_type": 3,
        "categories": {
            "Ground": {
                "default_type": 1,
                "types": [1, 9, 10, 12, 13],
            },
            "Grass & Crops": {
                "default_type": 3,
                "types": [2, 3, 8, 11],
            },
            "Trees": {
                "default_type": 4,
                "types": [4, 5, 6, 7, 17, 18],
            },
            "Shrubs & Wetlands": {
                "default_type": 15,
                "types": [14, 15, 16],
            },
        },
        "types": {
            1: {
                "label": "bare soil",
                "soil_type": 1,
                "display": {"color": "#8c564b"},
            },
            2: {
                "label": "crops, mixed farming",
                "soil_type": 2,
                "display": {"color": "#8c8931"},
            },
            3: {
                "label": "short grass",
                "soil_type": 3,
                "display": {"color": "#348C31"},
            },
            4: {
                "label": "evergreen needleleaf trees",
                "soil_type": 3,
                "display": {"color": "darkgreen"},
            },
            5: {
                "label": "deciduous needleleaf trees",
                "soil_type": 3,
                "display": {"color": "forestgreen"},
            },
            6: {
                "label": "evergreen broadleaf trees",
                "soil_type": 3,
                "display": {"color": "limegreen"},
            },
            7: {
                "label": "deciduous broadleaf trees",
                "soil_type": 3,
                "display": {"color": "olivedrab"},
            },
            8: {
                "label": "tall grass",
                "soil_type": 3,
                "display": {"color": "#2D7A2A"},
            },
            9: {
                "label": "desert",
                "soil_type": 1,
                "display": {"color": "khaki"},
            },
            10: {
                "label": "tundra",
                "soil_type": 4,
                "display": {"color": "darkseagreen"},
            },
            11: {
                "label": "irrigated crops",
                "soil_type": 3,
                "display": {"color": "chartreuse"},
            },
            12: {
                "label": "semidesert",
                "soil_type": 2,
                "display": {"color": "tan"},
            },
            13: {
                "label": "ice caps and glaciers",
                "soil_type": 1,
                "display": {"color": "aliceblue"},
            },
            14: {
                "label": "bogs and marshes",
                "soil_type": 6,
                "display": {"color": "mediumseagreen"},
            },
            15: {
                "label": "evergreen shrubs",
                "soil_type": 3,
                "display": {"color": "seagreen"},
            },
            16: {
                "label": "deciduous shrubs",
                "soil_type": 3,
                "display": {"color": "yellowgreen"},
            },
            17: {
                "label": "mixed forest/woodland",
                "soil_type": 3,
                "display": {"color": "#008b00"},
            },
            18: {
                "label": "interrupted forest",
                "soil_type": 3,
                "display": {"color": "darkolivegreen"},
            },
        },
    },

    "soil": {
        "default_type": 3,
        "types": {
            1: {
                "label": "Coarse",
                "display": {"color": "#d8c59f"},
            },
            2: {
                "label": "Medium",
                "display": {"color": "#c7ab7c"},
            },
            3: {
                "label": "Medium-fine",
                "display": {"color": "#b18f5f"},
            },
            4: {
                "label": "Fine",
                "display": {"color": "#9a774d"},
            },
            5: {
                "label": "Very fine",
                "display": {"color": "#7f613f"},
            },
            6: {
                "label": "Organic",
                "display": {"color": "#4f3c2c"},
            },
        },
    },

    "pavement": {
        "categories": {
            "Roads": {
                "default_type": 1,
                "types": [1, 2, 3],
            },
            "Stone paving": {
                "default_type": 5,
                "types": [4, 5, 6],
            },
            "Special materials": {
                "default_type": 7,
                "types": [7, 8],
            },
            "Gravel & Chips": {
                "default_type": 9,
                "types": [9, 10, 11, 12],
            },
            "Sports surfaces": {
                "default_type": 13,
                "types": [13, 14, 15],
            },
        },

        "default_type": 1,

        "street_types": {
            1: "unclassified",
            2: "cycleway",
            3: "footway / pedestrian",
            4: "path",
            5: "track",
            6: "living street",
            7: "service",
            8: "residential",
            9: "tertiary",
            10: "tertiary link",
            11: "secondary",
            12: "secondary link",
            13: "primary",
            14: "primary link",
            15: "trunk",
            16: "trunk link",
            17: "motorway",
            18: "motorway link",
            19: "raceway",
        },

        "types": {
            1: {"label": "Asphalt/concrete mix",
                "soil_type": 3, 
                "display": {"color": "#696969"}
            },
            2: {"label": "Asphalt (asphalt concrete)",
                "soil_type": 3, 
                "display": {"color": "#808080"}
            },
            3: {"label": "Concrete (Portland concrete)", 
                "soil_type": 3,
                "display": {"color": "#d3d3d3"}
            },
            4: {"label": "Sett", 
                "soil_type": 3,
                "display": {"color": "#708090"}
            },
            5: {"label": "Paving stones", 
                "soil_type": 3,
                "display": {"color": "#a9a9a9"}
            },
            6: {"label": "Cobblestone", 
                "soil_type": 3,
                "display": {"color": "#dcdcdc"}
            },
            7: {"label": "Metal", 
                "soil_type": 3,
                "display": {"color": "#c0c0c0"}
            },
            8: {"label": "Wood", 
                "soil_type": 3,
                "display": {"color": "#8b4513"}
            },
            9: {"label": "Gravel", 
                "soil_type": 3,
                "display": {"color": "#706047"}
            },
            10: {"label": "Fine gravel", 
                 "soil_type": 3,
                 "display": {"color": "#deb887"}
            },
            11: {"label": "Pebblestone", 
                 "soil_type": 3,
                 "display": {"color": "#f5f5dc"}
            },
            12: {"label": "Woodchips", 
                 "soil_type": 3,
                 "display": {"color": "#cd853f"}
            },
            13: {"label": "Tartan (sports)", 
                 "soil_type": 3,
                 "display": {"color": "#b22222"}
            },
            14: {"label": "Artificial turf (sports)", 
                 "soil_type": 3,
                 "display": {"color": "#32cd32"}
            },
            15: {"label": "Clay (sports)", 
                 "soil_type": 3,
                 "display": {"color": "#d2691e"}
            },
        },
    },
   "water": {
        "categories": {
            "Natural water": {
                "default_type": 1,
                "types": [1, 2, 3, 4],
            },
            "Urban water": {
                "default_type": 5,
                "types": [5],
            },
        },

        "default_type": 1,

        "types": {
            1: {
                "label": "Lake",
                "water_temperature": 283.0,
                "z0_water": 0.001,
                "z0h_water": 0.00001,
                "lambda_s": 1e10,
                "lambda_u": 1e10,
                "albedo_type": 1,
                "emissivity": 0.95,
                "display": {"color": "royalblue"},
            },
            2: {
                "label": "River",
                "water_temperature": 283.0,
                "z0_water": 0.003,
                "z0h_water": 0.00003,
                "lambda_s": 1e10,
                "lambda_u": 1e10,
                "albedo_type": 1,
                "emissivity": 0.95,
                "display": {"color": "deepskyblue"},
            },
            3: {
                "label": "Ocean",
                "water_temperature": 283.0,
                "z0_water": 0.001,
                "z0h_water": 0.00001,
                "lambda_s": 1e10,
                "lambda_u": 1e10,
                "albedo_type": 1,
                "emissivity": 0.95,
                "display": {"color": "navy"},
            },
            4: {
                "label": "Pond",
                "water_temperature": 283.0,
                "z0_water": 0.001,
                "z0h_water": 0.00001,
                "lambda_s": 1e10,
                "lambda_u": 1e10,
                "albedo_type": 1,
                "emissivity": 0.95,
                "display": {"color": "dodgerblue"},
            },
            5: {
                "label": "Fountain",
                "water_temperature": 283.0,
                "z0_water": 0.01,
                "z0h_water": 0.001,
                "lambda_s": 1e10,
                "lambda_u": 1e10,
                "albedo_type": 1,
                "emissivity": 0.95,
                "display": {"color": "turquoise"},
            },
        },
    },
}


# The 12 entries of vegetation_pars (index, name, unit), from PALM's static.yml
# (dimension nvegetation_pars). A set value replaces the default of the cell's
# vegetation_type, the fill value keeps the default.
VEGETATION_PARAMETERS = (
    ("minimum canopy resistance", "s m-1"),
    ("leaf area index", "m2 m-2"),
    ("vegetation coverage", ""),
    ("canopy resistance coefficient", "hPa-1"),
    ("roughness length for momentum", "m"),
    ("roughness length for heat", "m"),
    ("heat transfer coefficient skin to soil, stable", "W m-2 K-1"),
    ("heat transfer coefficient skin to soil, unstable", "W m-2 K-1"),
    ("shortwave fraction transmitted to soil (not implemented)", ""),
    ("heat capacity of the surface", "J m-2 K-1"),
    ("albedo type", ""),
    ("surface emissivity", ""),
)


# PALM's default roughness lengths z0 and z0h in m per vegetation type
# (land_surface_model_mod.f90, vegetation_pars indices 4 and 5) and for all
# pavement types (pavement_pars indices 0 and 1). Water types carry
# z0_water / z0h_water in SURFACE_CONFIG.
PALM_VEGETATION_ROUGHNESS = {
    1: (0.005, 0.5e-4), 2: (0.10, 0.001), 3: (0.03, 0.3e-4), 4: (2.0, 2.0),
    5: (2.0, 2.0), 6: (2.0, 2.0), 7: (2.0, 2.0), 8: (0.47, 0.47e-2),
    9: (0.013, 0.013e-2), 10: (0.034, 0.034e-2), 11: (0.5, 0.5e-2), 12: (0.17, 0.17e-2),
    13: (1.3e-3, 1.3e-4), 14: (0.83, 0.83e-2), 15: (0.10, 0.10e-2), 16: (0.25, 0.25e-2),
    17: (2.0, 2.0), 18: (1.10, 1.10),
}
PALM_PAVEMENT_ROUGHNESS = (0.05, 0.5e-3)
