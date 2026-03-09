SURFACE_CONFIG = {
    "vegetation": {
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
                "display": {"color": "brown"},
            },
            2: {
                "label": "crops, mixed farming",
                "soil_type": 2,
                "display": {"color": "yellowgreen"},
            },
            3: {
                "label": "short grass",
                "soil_type": 3,
                "display": {"color": "green"},
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
                "display": {"color": "lawngreen"},
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
                "display": {"color": "green4"},
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

        "types": {
            1: {"label": "Asphalt/concrete mix",
                "soil_type": 3, 
                "display": {"color": "gray"}
            },
            2: {"label": "Asphalt (asphalt concrete)",
                "soil_type": 3, 
                "display": {"color": "dimgray"}
            },
            3: {"label": "Concrete (Portland concrete)", 
                "soil_type": 3,
                "display": {"color": "lightgray"}
            },
            4: {"label": "Sett", 
                "soil_type": 3,
                "display": {"color": "slategray"}
            },
            5: {"label": "Paving stones", 
                "soil_type": 3,
                "display": {"color": "darkgray"}
            },
            6: {"label": "Cobblestone", 
                "soil_type": 3,
                "display": {"color": "gainsboro"}
            },
            7: {"label": "Metal", 
                "soil_type": 3,
                "display": {"color": "silver"}
            },
            8: {"label": "Wood", 
                "soil_type": 3,
                "display": {"color": "saddlebrown"}
            },
            9: {"label": "Gravel", 
                "soil_type": 3,
                "display": {"color": "tan"}
            },
            10: {"label": "Fine gravel", 
                 "soil_type": 3,
                 "display": {"color": "burlywood"}
            },
            11: {"label": "Pebblestone", 
                 "soil_type": 3,
                 "display": {"color": "linen"}
            },
            12: {"label": "Woodchips", 
                 "soil_type": 3,
                 "display": {"color": "peru"}
            },
            13: {"label": "Tartan (sports)", 
                 "soil_type": 3,
                 "display": {"color": "firebrick"}
            },
            14: {"label": "Artificial turf (sports)", 
                 "soil_type": 3,
                 "display": {"color": "limegreen"}
            },
            15: {"label": "Clay (sports)", 
                 "soil_type": 3,
                 "display": {"color": "chocolate"}
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