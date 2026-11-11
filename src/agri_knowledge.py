"""
Reference facts for every disease and pest the models can report. The advisor LLM receives the facts
for the detected labels and must base its advice on them, so a small model cannot, for example,
recommend a fungicide against a virus. Facts are general IPM guidance; doses are deliberately left
to product labels and the local agriculture officer.
"""
from __future__ import annotations

_BACTERIAL_SPOT = [
    "Cause: bacteria (Xanthomonas). Spreads by rain splash, overhead watering, infected seed and transplants.",
    "Remove and destroy badly spotted leaves; do not work in the field when plants are wet.",
    "Avoid overhead irrigation; water at the base.",
    "Copper-based bactericides can slow spread when used as the label says; they do not cure infected leaves.",
    "Prevention: disease-free seed and seedlings, 2-3 year crop rotation away from tomato/pepper/chilli.",
]
_EARLY_BLIGHT = [
    "Cause: fungus (Alternaria solani). Brown spots with target-like rings, starting on older lower leaves.",
    "Favoured by warm, humid weather and leaves staying wet.",
    "Remove infected lower leaves; mulch the soil to stop spores splashing up; water at the base.",
    "Protective fungicides (for example mancozeb or chlorothalonil types) as per label and local officer.",
    "Prevention: crop rotation, remove crop debris after harvest, balanced fertiliser (avoid nitrogen shortage).",
]
_LATE_BLIGHT = [
    "Cause: water mould (Phytophthora infestans). Spreads very fast in cool, wet, cloudy weather; can destroy a field within days.",
    "Act immediately: uproot and destroy (burn or bury) infected plants; never leave them in heaps near the field.",
    "Protective fungicides (mancozeb type) and systemic ones (metalaxyl/cymoxanil types) as per label and local officer.",
    "Avoid overhead irrigation; improve drainage and air flow.",
    "Prevention: certified disease-free seed tubers/seedlings; do not plant near infected potato or tomato fields.",
]

DISEASE_FACTS: dict[str, list[str]] = {
    "Pepper__bell___Bacterial_spot": _BACTERIAL_SPOT,
    "Tomato_Bacterial_spot": _BACTERIAL_SPOT,
    "Potato___Early_blight": _EARLY_BLIGHT,
    "Tomato_Early_blight": _EARLY_BLIGHT,
    "Potato___Late_blight": _LATE_BLIGHT,
    "Tomato_Late_blight": _LATE_BLIGHT,
    "Tomato_Leaf_Mold": [
        "Cause: fungus (Passalora fulva). Yellow patches on top of leaves, olive-green mould underneath.",
        "Favoured by very humid air (above 85%), common in poly-houses and dense planting.",
        "Improve ventilation and spacing, reduce humidity, remove affected leaves.",
        "Fungicides as per label and local officer; resistant varieties help.",
    ],
    "Tomato_Septoria_leaf_spot": [
        "Cause: fungus (Septoria lycopersici). Many small round spots with grey centres and dark edges, lower leaves first.",
        "Spreads by rain splash and wet leaves.",
        "Remove infected lower leaves, mulch the soil, avoid overhead watering.",
        "Protective fungicides as per label and local officer; rotate crops and clear debris after harvest.",
    ],
    "Tomato_Spider_mites_Two_spotted_spider_mite": [
        "Cause: spider mites (Tetranychus urticae), tiny pests, not a disease. Leaves get fine yellow speckles and webbing underneath.",
        "Worse in hot, dry, dusty conditions.",
        "Spray water on the underside of leaves; neem oil or insecticidal soap on leaf undersides.",
        "If severe, use a miticide (acaricide) as per label; avoid broad-spectrum insecticides that kill natural predators of mites.",
    ],
    "Tomato__Target_Spot": [
        "Cause: fungus (Corynespora cassiicola). Brown spots with rings on leaves, stems and fruit.",
        "Favoured by warm, humid weather and dense canopy.",
        "Remove infected leaves and crop debris; improve air flow; avoid overhead watering.",
        "Fungicides as per label and local officer; crop rotation.",
    ],
    "Tomato__Tomato_YellowLeaf__Curl_Virus": [
        "Cause: a VIRUS (TYLCV) spread by whiteflies (Bemisia tabaci). There is no cure for infected plants.",
        "Fungicides and bactericides (including copper) do NOT work against this virus - do not recommend them.",
        "Uproot and destroy infected plants early so whiteflies cannot carry the virus to healthy plants.",
        "Control whiteflies: yellow sticky traps, neem oil, and insecticides for whitefly as per label and local officer.",
        "Prevention: raise seedlings under insect-proof net, remove weeds that host whiteflies, grow TYLCV-resistant varieties.",
    ],
    "Tomato__Tomato_mosaic_virus": [
        "Cause: a VIRUS (Tomato mosaic virus) spread by touch - hands, tools, clothes - and by infected seed. There is no cure.",
        "Fungicides and insecticides do NOT cure it - do not recommend them for this virus.",
        "Remove and destroy infected plants; wash hands and tools with soap after touching them.",
        "Do not smoke or handle tobacco near plants; use certified seed and resistant varieties.",
    ],
    "Pepper__bell___healthy": ["The leaf looks healthy. No treatment is needed; keep monitoring."],
    "Potato___healthy": ["The leaf looks healthy. No treatment is needed; keep monitoring."],
    "Tomato_healthy": ["The leaf looks healthy. No treatment is needed; keep monitoring."],
}

_HEALTHY = ["The leaf looks healthy. No treatment is needed; keep monitoring."]

# Crops added with the 48-class model (rice, banana, PlantVillage crops)
DISEASE_FACTS.update({
    "Rice_blast": [
        "Cause: fungus (Magnaporthe oryzae). Diamond-shaped spots with grey centres and brown edges; can also rot the neck of the panicle.",
        "Favoured by cool nights, long leaf wetness, dense planting and too much nitrogen.",
        "Split nitrogen into smaller doses; avoid excess urea; keep the field free of grassy weeds.",
        "Fungicides such as tricyclazole or azoxystrobin types as per label and local agriculture officer.",
        "Prevention: blast-resistant varieties, seed treatment, destroy infected straw and stubble.",
    ],
    "Rice_bacterial_blight": [
        "Cause: bacteria (Xanthomonas oryzae). Leaves dry from the tip and edges with wavy yellow-white margins.",
        "There is no chemical cure for infected leaves; fungicides do not work against bacteria.",
        "Drain excess water, avoid excess nitrogen, and do not clip seedling tips at transplanting.",
        "Copper-based bactericides may slow spread only as the label and local officer advise.",
        "Prevention: resistant varieties, clean seed, remove weed hosts and infected stubble.",
    ],
    "Rice_brown_spot": [
        "Cause: fungus (Bipolaris oryzae). Oval brown spots with grey centres; common where soil is poor in potash or silicon.",
        "Correct the soil: apply potash and balanced fertiliser based on a soil test.",
        "Protective fungicides (for example mancozeb or propiconazole types) as per label and local officer.",
        "Prevention: healthy seed, seed treatment, good water management.",
    ],
    "Rice_tungro": [
        "Cause: VIRUSES spread by the green leafhopper. Plants turn yellow-orange and stay stunted. There is no cure.",
        "Fungicides do NOT work against this virus - do not recommend them.",
        "Uproot and destroy infected plants early; control green leafhoppers as per label and local officer.",
        "Prevention: tungro-resistant varieties, synchronous planting with neighbours, light traps to monitor leafhoppers.",
    ],
    "Rice_healthy": _HEALTHY,
    "Banana_sigatoka": [
        "Cause: fungus (Pseudocercospora). Yellow streaks turn into brown-black spots; leaves dry early and fruit stays small.",
        "Cut and remove badly spotted leaves and destroy them away from the field.",
        "Improve drainage and spacing; remove extra suckers to keep air moving.",
        "Fungicides such as propiconazole types, often with mineral oil, as per label and local officer.",
    ],
    "Banana_cordana": [
        "Cause: fungus (Cordana musae). Pale brown oval spots with yellow halos, often along leaf edges.",
        "Remove and destroy affected leaves; keep the plantation clean and well drained.",
        "Protective fungicides (for example mancozeb types) as per label and local officer.",
    ],
    "Banana_pestalotiopsis": [
        "Cause: fungus (Pestalotiopsis). Grey-brown spots, often entering through wounds.",
        "Remove infected leaves; avoid wounding leaves during field work.",
        "Copper or other protective fungicides as per label and local officer.",
    ],
    "Banana_healthy": _HEALTHY,
    "Maize_common_rust": [
        "Cause: fungus (Puccinia sorghi). Small brick-red powdery pustules on both leaf sides.",
        "Usually mild; spraying is needed only when many leaves are covered before tasselling.",
        "Fungicides (for example mancozeb or triazole types) as per label and local officer.",
        "Prevention: resistant hybrids and timely sowing.",
    ],
    "Maize_northern_leaf_blight": [
        "Cause: fungus (Exserohilum turcicum). Long cigar-shaped grey-green to tan lesions.",
        "Favoured by moderate temperatures and heavy dew.",
        "Fungicides (for example mancozeb or azoxystrobin types) as per label and local officer if it spreads before silking.",
        "Prevention: resistant hybrids, crop rotation, bury or remove infected crop residue.",
    ],
    "Maize_gray_leaf_spot": [
        "Cause: fungus (Cercospora zeae-maydis). Rectangular grey-tan lesions limited by leaf veins.",
        "Favoured by warm, humid weather and maize grown after maize.",
        "Fungicides (strobilurin or triazole types) as per label and local officer.",
        "Prevention: rotation, residue management, tolerant hybrids.",
    ],
    "Maize_healthy": _HEALTHY,
    "Apple_scab": [
        "Cause: fungus (Venturia inaequalis). Olive-green to black velvety spots on leaves and fruit.",
        "Rake and destroy fallen leaves; prune for an open canopy.",
        "Protective fungicides through wet periods, as per label and local officer.",
    ],
    "Apple_black_rot": [
        "Cause: fungus (Botryosphaeria obtusa). Purple-edged frog-eye leaf spots, fruit rot and branch cankers.",
        "Prune out dead wood and cankers; remove mummified fruit.",
        "Fungicides as per label and local officer.",
    ],
    "Apple_cedar_rust": [
        "Cause: fungus (Gymnosporangium) that alternates between apple and juniper/cedar trees. Bright orange leaf spots.",
        "Remove nearby juniper/cedar hosts where possible.",
        "Protective fungicides during spring as per label and local officer.",
    ],
    "Apple_healthy": _HEALTHY,
    "Grape_black_rot": [
        "Cause: fungus (Guignardia bidwellii). Brown leaf spots with dark borders; berries shrivel into black mummies.",
        "Remove mummified berries and infected leaves; keep the canopy open.",
        "Protective fungicides from early shoot growth as per label and local officer.",
    ],
    "Grape_esca": [
        "Cause: wood-rotting fungi (esca / black measles). Tiger-stripe leaf patterns; vines may collapse suddenly.",
        "No spray cures infected wood. Cut out dead arms well below the damage; protect large pruning wounds.",
        "Prune in dry weather and disinfect pruning tools.",
    ],
    "Grape_leaf_blight": [
        "Cause: fungus (Pseudocercospora / Isariopsis). Irregular dark brown spots; leaves fall early.",
        "Remove infected leaves; improve air flow in the canopy.",
        "Fungicides (for example mancozeb or copper types) as per label and local officer.",
    ],
    "Grape_healthy": _HEALTHY,
    "Orange_citrus_greening": [
        "Cause: BACTERIA (Huanglongbing) spread by the Asian citrus psyllid. Blotchy yellow mottling; bitter, lopsided fruit. There is no cure.",
        "Fungicides do NOT work. Remove and destroy infected trees so they do not infect others.",
        "Control the psyllid insect as per label and local officer; plant only certified disease-free saplings.",
    ],
    "Peach_bacterial_spot": [
        "Cause: bacteria (Xanthomonas arboricola). Small angular spots that fall out leaving shot-holes.",
        "Copper bactericides at the right stage can slow spread as per label and local officer; they do not cure.",
        "Prevention: resistant varieties, balanced nitrogen, windbreaks.",
    ],
    "Peach_healthy": _HEALTHY,
    "Cherry_powdery_mildew": [
        "Cause: fungus (Podosphaera). White powdery patches on young leaves.",
        "Prune for air flow; avoid excess nitrogen.",
        "Sulphur or other fungicides as per label and local officer.",
    ],
    "Cherry_healthy": _HEALTHY,
    "Squash_powdery_mildew": [
        "Cause: fungus. White powdery patches on leaves; common with dry days and humid nights.",
        "Remove the worst leaves; give plants space for air flow.",
        "Sulphur or other fungicides as per label and local officer; resistant varieties.",
    ],
    "Strawberry_leaf_scorch": [
        "Cause: fungus (Diplocarpon earliana). Many small purple spots that join so the leaf looks burnt.",
        "Remove infected leaves after harvest; avoid overhead watering.",
        "Fungicides as per label and local officer; plant disease-free runners.",
    ],
    "Strawberry_healthy": _HEALTHY,
    "Blueberry_healthy": _HEALTHY,
    "Raspberry_healthy": _HEALTHY,
    "Soybean_healthy": _HEALTHY,
    # Home-garden plants (pots, terraces, balconies)
    "Rose_leaf_spot": [
        "Cause: fungus, mostly black spot (Diplocarpon rosae). Round dark spots with feathery edges; the leaf turns yellow and falls.",
        "Pick off spotted leaves and fallen leaves and throw them away (not in compost).",
        "Water the soil, not the leaves, in the morning; give full sun and space for air.",
        "Neem oil helps prevent new spots; for bad cases a fungicide labelled for roses (for example mancozeb types) as per label.",
    ],
    "Rose_insect_damage": [
        "Chewing or sucking insects: caterpillars, beetles, leaf-cutter bees, aphids, thrips, or snails at night.",
        "Look under the leaves and around the pot in the evening and remove insects by hand or with a strong water spray.",
        "Spray neem oil (3-5 ml per litre with a drop of soap) in the evening; Bt spray for caterpillars.",
    ],
    "Rose_dry_leaf": [
        "Usually not a disease: too little water, hot sun on a terrace, a blocked pot drain, or old leaves at the bottom.",
        "Water deeply when the top 2-3 cm of soil is dry; check that water comes out of the drain hole.",
        "Mulch the pot and move it to afternoon shade in hot months; no spray is needed.",
    ],
    "Rose_nutrient_deficiency": [
        "Yellow leaves from hunger: old leaves yellow = nitrogen; young leaves yellow with green veins = iron; yellow between veins of old leaves = magnesium.",
        "Feed compost or a flowering-plant fertilizer every 2-4 weeks while the plant is growing.",
        "For yellow young leaves use chelated iron as per label; also check the pot drains, because wet roots cause yellowing too.",
    ],
    "Rose_healthy": _HEALTHY,
    "Money_plant_bacterial_wilt": [
        "Cause: bacteria. Water-soaked dark spots, yellowing and wilting stems; spreads in wet soil and wet leaves.",
        "No cure for infected parts: cut them off with clean scissors (wipe with spirit between cuts) and throw them away.",
        "Water less: let the top soil dry between waterings and never let the pot stand in water.",
        "Root healthy cuttings in fresh potting mix or clean water if the whole plant is affected.",
    ],
    "Money_plant_manganese_toxicity": [
        "Too much manganese: brown specks and yellowing between veins on older leaves, often after heavy fertilizer or in very acid soil.",
        "Flush the pot with plenty of clean water and stop micronutrient fertilizers for a few weeks.",
        "Repot in fresh potting mix if it does not improve.",
    ],
    "Money_plant_healthy": _HEALTHY,
    "Hibiscus_bacterial_leaf_spot": [
        "Cause: bacteria. Small dark water-soaked spots, often with a yellow ring; spreads with splashing water.",
        "Remove spotted leaves; water the soil, not the leaves.",
        "If it keeps spreading, a copper spray (copper oxychloride) as per label.",
    ],
    "Hibiscus_nutrient_deficiency": [
        "Yellow leaves: hibiscus in pots needs regular feeding; nitrogen, iron or magnesium run out first.",
        "Feed a flowering-plant fertilizer or compost every 2-3 weeks in the growing season.",
        "Yellow leaf with green veins: chelated iron, or magnesium sulphate (Epsom salt) as per label; check that the pot drains.",
    ],
    "Hibiscus_healthy": _HEALTHY,
    "Marigold_alternaria_blight": [
        "Cause: fungus (Alternaria). Brown-black spots with rings; leaves dry from the bottom of the plant up.",
        "Remove affected leaves; water at the base in the morning and keep space between plants.",
        "If it spreads, a mancozeb-type fungicide as per label.",
    ],
    "Marigold_pest_damage": [
        "Insects or mites: spider mites (speckled leaves, fine webs), thrips or caterpillars.",
        "Spray water under the leaves; spray neem oil (3-5 ml per litre) in the evening.",
        "Remove badly damaged leaves and check again after 3-4 days.",
    ],
    "Marigold_healthy": _HEALTHY,
})

PEST_FACTS: dict[str, list[str]] = {
    "aphids": [
        "Small soft sap-sucking insects in groups on young shoots and leaf undersides; leave sticky honeydew; can spread viruses.",
        "Spray strong water jets, neem oil or insecticidal soap; yellow sticky traps; protect ladybird beetles (natural enemies).",
        "If severe, an insecticide for aphids as per label and local officer.",
    ],
    "armyworm": [
        "Caterpillars that feed mostly at night and in groups; leave ragged holes and can strip leaves quickly.",
        "Check plants in the evening; hand-pick and destroy caterpillars and egg masses.",
        "Pheromone traps for monitoring; Bt (Bacillus thuringiensis) biopesticide on young caterpillars; insecticides as per label if severe.",
    ],
    "beetle": [
        "Leaf-eating beetles chew holes in leaves; adults and larvae can both feed.",
        "Hand-pick and destroy beetles in the morning; neem-based sprays deter feeding.",
        "Crop rotation and clearing crop debris reduce numbers; insecticides as per label only if damage is heavy.",
    ],
    "bollworm": [
        "Caterpillars (Helicoverpa armigera) that bore into buds, flowers, fruits and cotton bolls.",
        "Collect and destroy damaged fruits/bolls; pheromone traps for monitoring; bird perches in the field.",
        "Biopesticides (Bt, HaNPV) on young larvae; insecticides as per label and local officer when traps show high numbers.",
    ],
    "grasshopper": [
        "Chewing insects that eat leaf edges; outbreaks start from weedy field borders.",
        "Keep field borders weed-free; plough after harvest to expose eggs.",
        "Insecticides or baits as per label only if numbers are high.",
    ],
    "mites": [
        "Tiny spider mites (not insects) on leaf undersides; leaves get yellow speckles and fine webbing; worse in hot, dry weather.",
        "Spray water and neem oil or insecticidal soap on leaf undersides.",
        "If severe, a miticide (acaricide) as per label; avoid broad-spectrum insecticides that kill mite predators.",
    ],
    "mosquito": [
        "Mosquitoes do not damage crops; they breed in standing water.",
        "No crop treatment is needed; remove standing water around the field and home for health reasons.",
    ],
    "sawfly": [
        "Sawfly larvae look like caterpillars and eat leaves, sometimes in groups.",
        "Hand-pick larvae or prune infested shoots; insecticidal soap or neem on young larvae.",
        "Bt biopesticide does NOT work on sawfly larvae (they are not caterpillars); insecticides as per label if severe.",
    ],
    "stem_borer": [
        "Larvae bore into stems, causing 'dead heart' (dried central shoot) or white empty ears in rice.",
        "Pull out and destroy affected stems/tillers; destroy stubble after harvest.",
        "Pheromone traps; release Trichogramma egg-parasitoid cards; insecticides as per label and local officer.",
    ],
}


def facts_for(disease_label: str | None, pest_label: str | None) -> dict[str, list[str]]:
    out = {}
    if disease_label and disease_label in DISEASE_FACTS:
        out[disease_label] = DISEASE_FACTS[disease_label]
    if pest_label and pest_label in PEST_FACTS:
        out[pest_label] = PEST_FACTS[pest_label]
    return out
