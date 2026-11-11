"""
Precision Chemical & Organic Dosage Calculator
Calculates exact pesticide/fungicide/fertilizer mixing ratios
Based on field size, crop type, tank capacity, and pest/disease diagnosis
"""

from __future__ import annotations
from typing import Dict, Any, List, Optional


class DosageCalculator:
    """Calculates chemical and organic treatment dosages for crops"""

    # Comprehensive database of agricultural treatments
    TREATMENTS = {
        # PESTS
        "aphids": {
            "chemical": {
                "name": "Imidacloprid 17.8% SL (Confidor)",
                "dose_per_liter": 0.5,  # ml per liter
                "dose_unit": "ml",
                "water_volume_per_acre": 200,  # liters
                "total_per_acre": 100,  # ml
                "phi_days": 3,  # Pre-Harvest Interval (days)
                "safety_notes": "Wear gloves and respirator. Do not spray during bee foraging hours (early morning)."
            },
            "organic": {
                "name": "Neem Oil 10,000 PPM (Azadirachtin)",
                "dose_per_liter": 3.0,  # ml per liter
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 600,
                "phi_days": 0,
                "safety_notes": "Mix with a few drops of mild soap as emulsifier. Spray during cooler parts of the day."
            }
        },
        "armyworm": {
            "chemical": {
                "name": "Chlorantraniliprole 18.5% SC (Coragen)",
                "dose_per_liter": 0.4,
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 80,
                "phi_days": 3,
                "safety_notes": "Target early instar larvae. Thoroughly wet whorls and upper leaves."
            },
            "organic": {
                "name": "Bacillus thuringiensis (Bt - Dipel)",
                "dose_per_liter": 2.0,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 400,
                "phi_days": 0,
                "safety_notes": "Apply in late afternoon as UV light breaks down Bt bacteria."
            }
        },
        "bollworm": {
            "chemical": {
                "name": "Emamectin Benzoate 5% SG (Proclaim)",
                "dose_per_liter": 0.5,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 100,
                "phi_days": 3,
                "safety_notes": "Rapid translaminar action. Ensure complete coverage of flower buds and young fruits."
            },
            "organic": {
                "name": "Spinosad 45% SC",
                "dose_per_liter": 0.3,
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 60,
                "phi_days": 1,
                "safety_notes": "Naturally derived from soil actinomycete. Toxic to bees until dry."
            }
        },
        "mites": {
            "chemical": {
                "name": "Spiromesifen 22.9% SC (Oberon)",
                "dose_per_liter": 1.0,
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 200,
                "phi_days": 3,
                "safety_notes": "Spray undersides of leaves where two-spotted spider mites colonize."
            },
            "organic": {
                "name": "Wettable Sulfur 80% WP",
                "dose_per_liter": 2.5,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 500,
                "phi_days": 0,
                "safety_notes": "Do not apply when temperatures exceed 32°C (90°F) to prevent leaf scorching."
            }
        },
        "beetle": {
            "chemical": {
                "name": "Cypermethrin 10% EC",
                "dose_per_liter": 1.0,
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 200,
                "phi_days": 7,
                "safety_notes": "Contact pyrethroid. Keep away from water bodies and aquatic life."
            },
            "organic": {
                "name": "Beauveria bassiana (Bio-Pesticide)",
                "dose_per_liter": 3.0,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 600,
                "phi_days": 0,
                "safety_notes": "Entomopathogenic fungus. Requires high relative humidity (>70%) for best efficacy."
            }
        },
        "stem_borer": {
            "chemical": {
                "name": "Cartap Hydrochloride 50% SP",
                "dose_per_liter": 2.0,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 400,
                "phi_days": 14,
                "safety_notes": "Apply at first sign of stem boring or dead-heart symptoms."
            },
            "organic": {
                "name": "Pheromone Trap + Trichogramma Cards",
                "dose_per_liter": 0.0,
                "dose_unit": "traps",
                "water_volume_per_acre": 0,
                "total_per_acre": 5,
                "phi_days": 0,
                "safety_notes": "Install 5-8 pheromone traps per acre to disrupt mating cycle."
            }
        },

        # DISEASES
        "Early Blight": {
            "chemical": {
                "name": "Mancozeb 75% WP (Dithane M-45) or Azoxystrobin",
                "dose_per_liter": 2.5,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 500,
                "phi_days": 5,
                "safety_notes": "Preventive and curative contact fungicide. Alternate with systemic fungicides."
            },
            "organic": {
                "name": "Copper Oxychloride 50% WP (Blitox)",
                "dose_per_liter": 2.5,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 500,
                "phi_days": 1,
                "safety_notes": "Broad spectrum copper barrier. Do not apply during extreme heat."
            }
        },
        "Late Blight": {
            "chemical": {
                "name": "Metalaxyl 8% + Mancozeb 64% WP (Ridomil Gold)",
                "dose_per_liter": 2.5,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 500,
                "phi_days": 7,
                "safety_notes": "Systemic + contact fungicide. Essential in cold, wet, humid weather."
            },
            "organic": {
                "name": "Bordeaux Mixture (1:1:100)",
                "dose_per_liter": 10.0,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 2000,
                "phi_days": 0,
                "safety_notes": "Copper sulfate + slaked lime. Traditional, highly effective organic fungicide."
            }
        },
        "Bacterial Spot": {
            "chemical": {
                "name": "Streptomycin Sulphate 9% + Tetracycline 1% (Plantomycin)",
                "dose_per_liter": 0.5,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 100,
                "phi_days": 7,
                "safety_notes": "Tank-mix with Copper Oxychloride (2g/L) for synergistic bactericidal action."
            },
            "organic": {
                "name": "Pseudomonas fluorescens (Bio-Bactericide)",
                "dose_per_liter": 5.0,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 1000,
                "phi_days": 0,
                "safety_notes": "Beneficial rhizobacteria that produce antimicrobial metabolites."
            }
        },
        "Leaf Mold": {
            "chemical": {
                "name": "Difenoconazole 25% EC (Score)",
                "dose_per_liter": 0.5,
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 100,
                "phi_days": 3,
                "safety_notes": "Triazole systemic fungicide. Improve greenhouse/tunnel ventilation immediately."
            },
            "organic": {
                "name": "Potassium Bicarbonate (0.5% solution)",
                "dose_per_liter": 5.0,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 1000,
                "phi_days": 0,
                "safety_notes": "Raises leaf surface pH, killing fungal mycelium without synthetic chemicals."
            }
        },
        "Yellow Leaf Curl Virus": {
            "chemical": {
                "name": "Vector Control: Thiamethoxam 25% WG (Actara)",
                "dose_per_liter": 0.3,
                "dose_unit": "grams",
                "water_volume_per_acre": 200,
                "total_per_acre": 60,
                "phi_days": 5,
                "safety_notes": "Viruses cannot be cured directly; control the Whitefly vector immediately."
            },
            "organic": {
                "name": "Yellow Sticky Traps + Neem Seed Kernel Extract (5%)",
                "dose_per_liter": 50.0,
                "dose_unit": "ml",
                "water_volume_per_acre": 200,
                "total_per_acre": 10000,
                "phi_days": 0,
                "safety_notes": "Install 20 yellow sticky traps per acre to capture whitefly vectors."
            }
        }
    }

    @classmethod
    def calculate_dosage(
        cls,
        target_name: str,
        field_size_acres: float = 1.0,
        tank_capacity_liters: float = 15.0,  # Standard knapsack tank
        preferred_mode: str = "both"  # "chemical", "organic", or "both"
    ) -> Dict[str, Any]:
        """
        Calculate customized spray dosages

        Args:
            target_name: Name of pest or disease (e.g., "aphids", "Early Blight")
            field_size_acres: Farm area in acres
            tank_capacity_liters: Capacity of farmer's sprayer tank (default 15L knapsack)
            preferred_mode: "chemical", "organic", or "both"

        Returns:
            Dictionary with mixing ratios, total quantities, tank counts, and safety instructions
        """
        # Clean and normalize target string
        norm_target = target_name.lower().replace("_", " ").replace("(uncertain)", "").strip()

        # Find matching key in treatment database
        matched_key = None
        for key in cls.TREATMENTS:
            norm_key = key.lower().replace("_", " ").strip()
            if norm_key in norm_target or norm_target in norm_key:
                matched_key = key
                break

        if not matched_key:
            # Check individual word overlaps
            target_words = set(norm_target.split())
            for key in cls.TREATMENTS:
                key_words = set(key.lower().replace("_", " ").split())
                if target_words & key_words - {"crop", "leaf", "plant", "spot", "disease", "pest"}:
                    matched_key = key
                    break

        if not matched_key:
            # Fallback general recommendation
            return cls._generate_generic_dosage(target_name, field_size_acres, tank_capacity_liters)

        treatment_info = cls.TREATMENTS[matched_key]
        total_water_liters = round(field_size_acres * 200.0, 1)  # Standard 200L water per acre
        num_tanks = round(total_water_liters / max(tank_capacity_liters, 1), 1)

        result = {
            "ok": True,
            "target": target_name,
            "field_size_acres": field_size_acres,
            "sprayer_tank_liters": tank_capacity_liters,
            "total_water_needed_liters": total_water_liters,
            "number_of_tanks_required": num_tanks,
            "chemical_treatment": None,
            "organic_treatment": None
        }

        # Calculate Chemical Plan
        if preferred_mode in ["chemical", "both"] and "chemical" in treatment_info:
            chem = treatment_info["chemical"]
            dose_per_tank = round(chem["dose_per_liter"] * tank_capacity_liters, 2)
            total_chem = round(chem["total_per_acre"] * field_size_acres, 2)

            result["chemical_treatment"] = {
                "product_name": chem["name"],
                "dose_per_liter": f"{chem['dose_per_liter']} {chem['dose_unit']}/L",
                "dose_per_knapsack_tank": f"{dose_per_tank} {chem['dose_unit']} in {tank_capacity_liters}L water",
                "total_product_for_field": f"{total_chem} {chem['dose_unit']}",
                "pre_harvest_interval_days": chem["phi_days"],
                "safety_and_application": chem["safety_notes"],
                "mixing_instructions": (
                    f"1. Fill sprayer tank half full with clean water.\n"
                    f"2. Add exactly {dose_per_tank} {chem['dose_unit']} of {chem['name']}.\n"
                    f"3. Fill remaining tank to {tank_capacity_liters}L and stir thoroughly.\n"
                    f"4. Spray evenly over {1 / max(num_tanks, 1):.2f} acres per tank."
                )
            }

        # Calculate Organic Plan
        if preferred_mode in ["organic", "both"] and "organic" in treatment_info:
            org = treatment_info["organic"]
            dose_per_tank = round(org["dose_per_liter"] * tank_capacity_liters, 2)
            total_org = round(org["total_per_acre"] * field_size_acres, 2)

            result["organic_treatment"] = {
                "product_name": org["name"],
                "dose_per_liter": f"{org['dose_per_liter']} {org['dose_unit']}/L",
                "dose_per_knapsack_tank": f"{dose_per_tank} {org['dose_unit']} in {tank_capacity_liters}L water",
                "total_product_for_field": f"{total_org} {org['dose_unit']}",
                "pre_harvest_interval_days": org["phi_days"],
                "safety_and_application": org["safety_notes"],
                "mixing_instructions": (
                    f"1. Mix {dose_per_tank} {org['dose_unit']} of {org['name']} into a small bucket with lukewarm water.\n"
                    f"2. Pour into {tank_capacity_liters}L knapsack sprayer and top up with clean water.\n"
                    f"3. Apply in evening or early morning to prevent photo-degradation."
                )
            }

        return result

    @classmethod
    def _generate_generic_dosage(cls, target_name: str, field_size: float, tank_liters: float) -> Dict[str, Any]:
        """Generic broad-spectrum dosage fallback"""
        water_needed = round(field_size * 200.0, 1)
        num_tanks = round(water_needed / max(tank_liters, 1), 1)

        return {
            "ok": True,
            "target": target_name,
            "field_size_acres": field_size,
            "sprayer_tank_liters": tank_liters,
            "total_water_needed_liters": water_needed,
            "number_of_tanks_required": num_tanks,
            "chemical_treatment": {
                "product_name": "Broad Spectrum Protective Fungicide/Insecticide",
                "dose_per_liter": "2.0 ml or g / Liter",
                "dose_per_knapsack_tank": f"{round(2.0 * tank_liters, 1)} ml/g per {tank_liters}L tank",
                "total_product_for_field": f"{round(400 * field_size, 1)} ml/g",
                "pre_harvest_interval_days": 7,
                "safety_and_application": "Consult local agricultural extension service for specific registered products.",
                "mixing_instructions": "Dilute thoroughly in clean water and spray evenly."
            },
            "organic_treatment": {
                "product_name": "Neem Oil 10,000 PPM + Organic Bio-Shield",
                "dose_per_liter": "3.0 ml / Liter",
                "dose_per_knapsack_tank": f"{round(3.0 * tank_liters, 1)} ml per {tank_liters}L tank",
                "total_product_for_field": f"{round(600 * field_size, 1)} ml",
                "pre_harvest_interval_days": 0,
                "safety_and_application": "Safe for pollinators after drying. Spray during low sunlight.",
                "mixing_instructions": "Mix with a small amount of liquid detergent as emulsifier."
            }
        }
