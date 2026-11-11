"""
Fertilizer bag calculator: turns an N-P-K recommendation (kg of N, P2O5 and K2O, as printed on the
Soil Health Card or given by the agriculture officer) into bags of Urea, DAP and MOP (potash).

Pure arithmetic on the fixed nutrient content of these fertilizers; it never invents a recommendation.
"""
from __future__ import annotations

import math

ACRES_PER_HECTARE = 2.471
# Nutrient fraction (Fertilizer Control Order grades) and the usual bag size in India
UREA_N = 0.46            # Urea 46-0-0, 45 kg bag
DAP_N, DAP_P = 0.18, 0.46  # DAP 18-46-0, 50 kg bag
MOP_K = 0.60             # Muriate of Potash 0-0-60, 50 kg bag
BAG_KG = {"Urea": 45, "DAP": 50, "MOP (Potash)": 50}


def plan(n: float, p2o5: float, k2o: float, acres: float, dose_per: str = "acre") -> dict:
    """kg and bags for the whole field. Doses are kg per acre (or per hectare when dose_per="hectare")."""
    scale = acres / ACRES_PER_HECTARE if dose_per == "hectare" else acres
    n, p2o5, k2o = n * scale, p2o5 * scale, k2o * scale
    dap = p2o5 / DAP_P            # all phosphorus from DAP
    n_from_dap = dap * DAP_N      # DAP also brings nitrogen, so less urea is needed
    urea = max(0.0, n - n_from_dap) / UREA_N
    mop = k2o / MOP_K
    items = []
    for name, kg, gives in (("Urea", urea, f"{n - min(n, n_from_dap):.1f} kg N"),
                            ("DAP", dap, f"{p2o5:.1f} kg P2O5 + {n_from_dap:.1f} kg N"),
                            ("MOP (Potash)", mop, f"{k2o:.1f} kg K2O")):
        bag = BAG_KG[name]
        items.append({"product": name, "kg": round(kg, 1), "bag_kg": bag, "bags": round(kg / bag, 2),
                      "bags_to_buy": math.ceil(round(kg / bag, 2)), "gives": gives})
    return {
        "items": items,
        "total_n_kg": round(n, 1), "total_p2o5_kg": round(p2o5, 1), "total_k2o_kg": round(k2o, 1),
        # DAP for the phosphorus already gives more nitrogen than asked for
        "extra_n_kg": round(max(0.0, n_from_dap - n), 1),
        "acres": acres, "dose_per": dose_per,
    }
