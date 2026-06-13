"""
brmangue/constants.py — BR-MANGUE Domain Constants
=========================================================
Land use and soil tables aligned with the original Lua model (Bezerra, 2014).
CRS and geographic parameters for Maranhão Island.
"""
from __future__ import annotations

# ── tabela_usos ───────────────────────────────────────────────────────────────
MANGUE                    = 1
VEGETACAO_TERRESTRE       = 2
MAR                       = 3
AREA_ANTROPIZADA          = 4
SOLO_DESCOBERTO           = 5
SOLO_INUNDADO             = 6
AREA_ANTROPIZADA_INUNDADA = 7
MANGUE_MIGRADO            = 8
MANGUE_INUNDADO           = 9
VEG_TERRESTRE_INUNDADA    = 10

USOS_INUNDADOS: list[int] = [
    MAR, SOLO_INUNDADO, AREA_ANTROPIZADA_INUNDADA,
    MANGUE_INUNDADO, VEG_TERRESTRE_INUNDADA,
]

# seco → inundado (Bezerra 2014)
REGRAS_INUNDACAO: dict[int, int] = {
    MANGUE:              MANGUE_INUNDADO,
    MANGUE_MIGRADO:      MANGUE_INUNDADO,
    VEGETACAO_TERRESTRE: VEG_TERRESTRE_INUNDADA,
    AREA_ANTROPIZADA:    AREA_ANTROPIZADA_INUNDADA,
    SOLO_DESCOBERTO:     SOLO_INUNDADO,
}

USO_LABELS: dict[int, str] = {
    MANGUE:                    "Mangue",
    VEGETACAO_TERRESTRE:       "Vegetação Terrestre",
    MAR:                       "Mar",
    AREA_ANTROPIZADA:          "Área Antropizada",
    SOLO_DESCOBERTO:           "Solo Descoberto",
    SOLO_INUNDADO:             "Solo Inundado",
    AREA_ANTROPIZADA_INUNDADA: "Área Antrop. Inundada",
    MANGUE_MIGRADO:            "Mangue Migrado",
    MANGUE_INUNDADO:           "Mangue Inundado",
    VEG_TERRESTRE_INUNDADA:    "Veg. Terrestre Inundada",
}

# cores exatas do Lua (tabela_usos RGB → hex)
USO_COLORS: dict[int, str] = {
    MANGUE:                    "#006400",
    VEGETACAO_TERRESTRE:       "#808000",
    MAR:                       "#00008b",
    AREA_ANTROPIZADA:          "#ffd700",
    SOLO_DESCOBERTO:           "#ffdead",
    SOLO_INUNDADO:             "#000000",
    AREA_ANTROPIZADA_INUNDADA: "#323232",
    MANGUE_MIGRADO:            "#00ff00",
    MANGUE_INUNDADO:           "#ff0000",
    VEG_TERRESTRE_INUNDADA:    "#000000",
}

# ── tabela_solos ──────────────────────────────────────────────────────────────
SOLO_CANAL_FLUVIAL  = 0
SOLO_LEITO_RIO      = 1   # present in input data — no active rule (legacy class)
SOLO_PODZOLICO      = 2   # present in input data — no active rule (legacy class)
SOLO_MANGUE         = 3
SOLO_OUTROS         = 4
SOLO_MANGUE_MIGRADO = 9

# All soil codes present in the input data. Values 1 and 2 are legacy classes
# from the original Bezerra (2014) database that carry no transition rule in
# the current model — they are treated as passive substrate (like SOLO_OUTROS).
VALID_SOLO: set[int] = {
    SOLO_CANAL_FLUVIAL,
    SOLO_LEITO_RIO,
    SOLO_PODZOLICO,
    SOLO_MANGUE,
    SOLO_OUTROS,
    SOLO_MANGUE_MIGRADO,
}

SOLO_LABELS: dict[int, str] = {
    SOLO_CANAL_FLUVIAL:  "Canal Fluvial",
    SOLO_LEITO_RIO:      "Leito de Rio",
    SOLO_PODZOLICO:      "Podzólico",
    SOLO_MANGUE:         "Mangue",
    SOLO_MANGUE_MIGRADO: "Mangue Migrado",
    SOLO_OUTROS:         "Outros",
}

# ── geografia — Ilha do Maranhão ──────────────────────────────────────────────
ORIGIN_X  = 500_000.0    # UTM Easting  (SIRGAS 2000 / UTM 24S)
ORIGIN_Y  = 9_700_000.0  # UTM Northing
CRS       = "EPSG:31984"
CELL_SIZE = 100.0         # metros

# ── GeoTIFF: especificação de bandas (nome, dtype numpy, nodata) ──────────────
TIFF_BANDS: list[tuple[str, str, float]] = [
    ("uso",  "int16",   0),
    ("alt",  "float32", -9999.0),
    ("solo", "int16",   -1),
]

# cores da tabela_solos (para RasterMap)
SOLO_COLORS: dict[int, str] = {
    SOLO_CANAL_FLUVIAL:  "#0000ff",   # azul — canal de drenagem
    SOLO_LEITO_RIO:      "#6699cc",   # azul claro
    SOLO_PODZOLICO:      "#aaaaaa",   # cinza claro
    SOLO_MANGUE:         "#006400",   # verde escuro
    SOLO_MANGUE_MIGRADO: "#228b22",   # verde floresta
    SOLO_OUTROS:         "#888888",   # cinza
}