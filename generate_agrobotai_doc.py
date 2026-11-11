import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

def create_document():
    doc = docx.Document()

    # Color Palette: Deep Forest Green (#1B4D3E), Emerald (#2E7D32), Charcoal (#212121)
    PRIMARY_COLOR = RGBColor(27, 77, 62)     # #1B4D3E
    SECONDARY_COLOR = RGBColor(46, 125, 50)  # #2E7D32
    TEXT_COLOR = RGBColor(33, 33, 33)        # #212121
    MUTED_COLOR = RGBColor(85, 85, 85)       # #555555
    WHITE = RGBColor(255, 255, 255)

    # Page Margins (1 inch all around)
    for section in doc.sections:
        section.top_margin = Inches(1.0)
        section.bottom_margin = Inches(1.0)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    # Helper function for cell background shading
    def set_cell_shading(cell, color_hex):
        shading = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{color_hex}"/>')
        cell._tc.get_or_add_tcPr().append(shading)

    # Helper function for cell padding
    def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
        tcPr = cell._tc.get_or_add_tcPr()
        tcMar = OxmlElement('w:tcMar')
        for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
            node = OxmlElement(f'w:{m}')
            node.set(qn('w:w'), str(val))
            node.set(qn('w:type'), 'dxa')
            tcMar.append(node)
        tcPr.append(tcMar)

    # Helper function for adding styled headings
    def add_heading_1(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(15)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR

        pBdr = parse_xml(f'<w:pBdr {nsdecls("w")}><w:bottom w:val="single" w:sz="12" w:space="4" w:color="2E7D32"/></w:pBdr>')
        p._p.get_or_add_pPr().append(pBdr)
        return p

    def add_heading_2(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(12.5)
        run.font.bold = True
        run.font.color.rgb = SECONDARY_COLOR
        return p

    def add_heading_3(text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(8)
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.keep_with_next = True
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(11)
        run.font.bold = True
        run.font.color.rgb = PRIMARY_COLOR
        return p

    def add_body_p(text, bold_prefix=None, italic=False):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = 'Calibri'
            r_pre.font.size = Pt(10.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = TEXT_COLOR
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(10.5)
        run.font.italic = italic
        run.font.color.rgb = TEXT_COLOR
        return p

    def add_bullet_p(text, bold_prefix=None):
        p = doc.add_paragraph(style='List Bullet')
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(3)
        p.paragraph_format.line_spacing = 1.15
        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = 'Calibri'
            r_pre.font.size = Pt(10.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = TEXT_COLOR
        run = p.add_run(text)
        run.font.name = 'Calibri'
        run.font.size = Pt(10.5)
        run.font.color.rgb = TEXT_COLOR
        return p

    # -------------------------------------------------------------
    # COVER / HEADER TITLE
    # -------------------------------------------------------------
    title_p = doc.add_paragraph()
    title_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    title_p.paragraph_format.space_before = Pt(10)
    title_p.paragraph_format.space_after = Pt(4)
    run_title = title_p.add_run("AGROBOTAI")
    run_title.font.name = 'Calibri'
    run_title.font.size = Pt(24)
    run_title.font.bold = True
    run_title.font.color.rgb = PRIMARY_COLOR

    subtitle_p = doc.add_paragraph()
    subtitle_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle_p.paragraph_format.space_before = Pt(0)
    subtitle_p.paragraph_format.space_after = Pt(14)
    run_sub = subtitle_p.add_run("Edge-AI & Multi-Sensor IoT Smart Farm Platform for Precision Crop Health, Soil Biochemical Profiling & Agronomy Advisory")
    run_sub.font.name = 'Calibri'
    run_sub.font.size = Pt(12.5)
    run_sub.font.bold = True
    run_sub.font.color.rgb = SECONDARY_COLOR

    # Meta banner table
    meta_table = doc.add_table(rows=1, cols=1)
    meta_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = meta_table.rows[0].cells[0]
    set_cell_shading(cell, "E8F5E9")
    set_cell_margins(cell, top=100, bottom=100, left=150, right=150)
    meta_p = cell.paragraphs[0]
    meta_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_meta = meta_p.add_run("MASTER PROJECT SPECIFICATION & ARCHITECTURE DOCUMENT\n")
    r_meta.font.bold = True
    r_meta.font.size = Pt(10)
    r_meta.font.color.rgb = PRIMARY_COLOR
    r_meta2 = meta_p.add_run("Focus: Edge AI (Raspberry Pi), Multi-Sensor Soil NPK/pH/Temp/Moisture Telemetry, Optical Chlorophyll/Stress Proxies, PyTorch Vision, Precision Spray Math & 10-Language Advisory")
    r_meta2.font.size = Pt(9.5)
    r_meta2.font.italic = True
    r_meta2.font.color.rgb = MUTED_COLOR

    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # -------------------------------------------------------------
    # 1. PROJECT TITLE
    # -------------------------------------------------------------
    add_heading_1("1. Project Title")
    add_body_p(
        "AGROBOTAI — Edge-AI & Multi-Sensor IoT Smart Farm Platform for Precision Crop Health, Soil Biochemical Profiling & Agronomy Advisory",
        bold_prefix="Official Project Title: "
    )
    add_body_p(
        "\"From On-Field Leaf Macro-Imaging and Multi-Sensor Soil Telemetry to Offline Edge AI Diagnostics, Chemical/Organic Precision Spray Math, and Multilingual Agronomist Advisory in 10 Regional Languages.\"",
        bold_prefix="Project Tagline: ",
        italic=True
    )

    # -------------------------------------------------------------
    # 2. ABSTRACT
    # -------------------------------------------------------------
    add_heading_1("2. Abstract")
    add_body_p(
        "Agriculture is the foundation of economic security for over 50% of India's population. However, farmers continually face devastating crop yield losses exceeding 30% to 40% annually due to insect pest infestations, foliar fungal/bacterial diseases, unmonitored soil nutrient deficiencies, and uncalibrated chemical pesticide application. Conventional digital agriculture solutions depend heavily on cloud infrastructure, making them unusable in rural agricultural areas with limited or non-existent internet connectivity. Furthermore, standard vision tools identify diseases only after severe necrotic lesions appear, missing crucial pre-symptomatic physiological stress and underlying soil biochemical imbalances."
    )
    add_body_p(
        "To resolve these challenges, this project develops AGROBOTAI, an enterprise-grade Edge-AI and Multi-Sensor IoT smart farming platform designed for autonomous, real-time agronomic intelligence directly on the farm. AGROBOTAI is anchored by an edge computing brain deployed on a Raspberry Pi (4B/5) interfaced with a Raspberry Pi Camera Module 3 (Autofocus macro lens) and a comprehensive array of IoT sensors: RS485 Modbus 7-in-1 soil probes (measuring Nitrogen, Phosphorus, Potassium, pH, Electrical Conductivity, Soil Moisture, and Soil Temperature), atmospheric DHT22 sensors, and autonomous 395nm solar UV insect light traps."
    )
    add_body_p(
        "At the vision layer, AGROBOTAI utilizes PyTorch deep learning models (EfficientNet-B0 / ConvNeXt) to identify 9 insect pest classes and 15 crop disease classes with visual Explainable AI (Grad-CAM heatmaps). To detect pre-symptomatic cellular stress before visible spots emerge, the platform calculates biophysical optical proxies: the Excess Green Index (ExG = 2G - R - B) for active chlorophyll estimation and Carotenoid Reflectance Indices (CRI1/CRI2). Quantitative disease severity is computed using semantic lesion segmentation across dual HSV and LAB color spaces into Stages 1 through 4."
    )
    add_body_p(
        "Beyond diagnosis, AGROBOTAI features a deterministic Precision Dosage & Tank Mix Calculator that computes exact milliliter/gram chemical volumes, dilution ratios, and tank refill counts based on acreage and sprayer capacity, accompanied by bio-organic alternatives (Neem oil, Trichoderma) and Pre-Harvest Intervals (PHI). A microclimate epidemiological model forecasts fungal/bacterial spore germination risks, while an integrated Multilingual Agronomist Chatbot provides voice and text guidance in 10 regional Indian languages. Capable of operating 100% offline at the farm gate, AGROBOTAI delivers an accessible, scientific, and sustainable precision farming solution."
    )

    # -------------------------------------------------------------
    # 3. EXISTING SYSTEM & DRAWBACKS
    # -------------------------------------------------------------
    add_heading_1("3. Existing System & Drawbacks")
    add_body_p(
        "In current agricultural practices, crop health monitoring and pest/disease management are predominantly manual, reactionary, and unscientific. Technological options remain fragmented and suffer from major limitations:"
    )

    add_heading_2("A. Limitations of Existing Practices")
    add_bullet_p("Farmers rely on visual inspection, spotting infections only after widespread chlorosis or necrosis has destroyed active leaf tissue.", "Manual Visual Scouting: ")
    add_bullet_p("Soil samples sent to testing labs take 2 to 3 weeks for reports, by which time the crop growth stage has advanced, rendering data obsolete.", "Delayed Soil Lab Testing: ")
    add_bullet_p("Pesticides are applied based on vendor guesses, resulting in chemical over-application, soil toxicity, environmental run-off, and pest resistance.", "Uncalibrated Chemical Spraying: ")
    add_bullet_p("Most modern agricultural AI mobile apps require uploading high-resolution photos to cloud servers, failing completely in rural offline zones.", "Cloud-Dependent Mobile Apps: ")
    add_bullet_p("Existing digital platforms operate only in English or standard Hindi, alienating millions of regional smallholder farmers.", "Language Accessibility Barrier: ")

    add_heading_2("B. Summary Table of Existing System Drawbacks")

    drawbacks_table = doc.add_table(rows=1, cols=3)
    drawbacks_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr_cells = drawbacks_table.rows[0].cells
    hdr_cells[0].text = "Parameter / Area"
    hdr_cells[1].text = "Existing System Limitation"
    hdr_cells[2].text = "Impact on Farmer & Crop"

    for c in hdr_cells:
        set_cell_shading(c, "1B4D3E")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE
        p.runs[0].font.size = Pt(9.5)

    drawback_data = [
        ("Connectivity Dependence", "Mandatory cloud server connection for image inference.", "Zero utility in offline rural farms without internet."),
        ("Detection Timing", "Only identifies late-stage visible lesions on leaves.", "Pre-symptomatic stress is missed; high yield loss occurs."),
        ("Soil & Foliar Disconnect", "Soil testing and leaf vision are treated as separate tools.", "Fails to correlate soil NPK/pH deficiency with foliar chlorosis."),
        ("Dosage Calibration", "Static label text without tank or field acreage calculation.", "Severe pesticide over-application or ineffective under-dosing."),
        ("Insect Pest Surveillance", "Manual sticky traps requiring physical counting.", "Delayed identification of nocturnal armyworms and bollworms."),
        ("Language Inclusivity", "Limited or no support for localized vernacular speech.", "Farmers unable to understand complex chemical recommendations.")
    ]

    for item in drawback_data:
        row = drawbacks_table.add_row()
        for idx, text in enumerate(item):
            cell = row.cells[idx]
            set_cell_margins(cell, 60, 60, 80, 80)
            if idx == 0:
                set_cell_shading(cell, "F1F8E9")
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.size = Pt(9)
            run.font.name = 'Calibri'
            if idx == 0:
                run.font.bold = True

    # -------------------------------------------------------------
    # 4. PROPOSED SYSTEM & KEY ADVANTAGES
    # -------------------------------------------------------------
    add_heading_1("4. Proposed System & Key Advantages")
    add_body_p(
        "AGROBOTAI delivers an integrated, multi-tiered Edge-AI and Multi-Sensor IoT architecture that unites physical sensor telemetry, multi-spectral optical proxies, deep learning vision models, precision dosage math, and multilingual conversational assistance into a single unified platform."
    )

    add_heading_2("A. Key Innovations & Advantages")
    add_bullet_p("All deep learning vision models, spectral analysis pipelines, databases, and web servers run locally on a Raspberry Pi 4B/5, ensuring 100% offline functionality at the farm gate.", "100% Offline Edge Computing on Raspberry Pi: ")
    add_bullet_p("RS485 Modbus 7-in-1 soil probes provide continuous telemetry of Nitrogen, Phosphorus, Potassium, pH, EC, soil moisture, and soil temperature.", "Comprehensive Soil & Microclimate IoT Array: ")
    add_bullet_p("Dual PyTorch models (EfficientNet-B0 / ConvNeXt) identify 9 pest species and 15 crop diseases with Grad-CAM visual heatmaps for diagnostic explainability.", "Dual Deep Learning Vision Engine: ")
    add_bullet_p("Calculates Excess Green Index (ExG) for active chlorophyll estimation and Carotenoid Reflectance Indices (CRI1/CRI2) to detect early cellular physiological stress before spots become visible.", "Optical Spectral Chlorophyll & Stress Proxies: ")
    add_bullet_p("Applies dual HSV and LAB color-space thresholding to segment necrotic and chlorotic tissue, determining exact surface damage percentage and classifying severity from Stage 1 (Mild) to Stage 4 (Critical).", "Quantitative Disease Severity Mapping: ")
    add_bullet_p("Dynamic calculator takes farmer's acreage and knapsack sprayer capacity (e.g., 16L) to compute exact chemical milliliters, dilution ratios, tank refills, organic bio-pesticides (Neem, Trichoderma), and Pre-Harvest Intervals (PHI).", "Precision Spray Dosage Engine: ")
    add_bullet_p("Epidemiological microclimate model predicts fungal and bacterial spore germination risks based on continuous ambient temperature, humidity, and moisture telemetry.", "Microclimate Weather Risk Forecaster: ")
    add_bullet_p("Full conversational chatbot support in 10 languages: English, Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, and Punjabi.", "10-Language Regional Agronomist: ")
    add_bullet_p("Direct GPIO relay triggering for solenoid drip valves and pump misting when moisture or health thresholds are breached.", "Autonomous Actuation & Relay Control: ")

    # -------------------------------------------------------------
    # 5. ARCHITECTURE DIAGRAM
    # -------------------------------------------------------------
    add_heading_1("5. Architecture Diagram & Detailed System Workflow")
    add_body_p(
        "The following diagram illustrates the complete edge-to-cloud architecture, hardware sensor integration, deep learning pipelines, and user interaction layers of AGROBOTAI:"
    )

    arch_box = doc.add_table(rows=1, cols=1)
    arch_box.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_arch = arch_box.rows[0].cells[0]
    set_cell_shading(c_arch, "FAFAFA")
    set_cell_margins(c_arch, 100, 100, 120, 120)
    p_arch = c_arch.paragraphs[0]
    p_arch.paragraph_format.line_spacing = 1.0

    diagram_text = """
========================================================================================================
                                      AGROBOTAI SYSTEM ARCHITECTURE
========================================================================================================

  +--------------------------------------------------------------------------------------------------+
  |                                   1. MULTI-SENSOR IOT & CAMERA INPUT                             |
  |                                                                                                  |
  |  [RS485 Modbus 7-in-1 Soil Sensor]   [DHT22 Microclimate]     [Capacitive Soil]  [Solar UV Trap] |
  |   - Nitrogen (N), Phosph. (P), Pot. (K) - Ambient Temp (C)    - Root Zone        - 395nm UV LEDs |
  |   - Soil pH, Salinity (EC), Moisture    - Rel. Humidity (%)     Moisture (%)     - ESP32-CAM     |
  |                                                                                                  |
  |                      [High-Definition Leaf Image Capture (RPi Cam 3 / Smartphone)]               |
  +-------------------------------------------------+------------------------------------------------+
                                                    | (RS485 Modbus / GPIO / Wi-Fi / MQTT)
                                                    v
  +--------------------------------------------------------------------------------------------------+
  |                             2. RASPBERRY PI 4B / 5 MASTER EDGE AI HUB                            |
  |                              (Runs 100% Offline at Farm-Gate or Base)                            |
  |                                                                                                  |
  |   +---------------------------------------+      +-------------------------------------------+   |
  |   |   A. DEEP LEARNING VISION PIPELINE    |      |    B. BIO-PHYSICAL & BIOCHEMICAL ENGINE   |   |
  |   |  - PyTorch Pest Model (9 Classes)     |      |  - ExG Optical Chlorophyll Density Finder |   |
  |   |  - PyTorch Disease Model (15 Classes) |      |  - CRI1 & CRI2 Pre-Symptomatic Stress     |   |
  |   |  - Grad-CAM Visual Heatmap Generation |      |  - Dual HSV/LAB Lesion Severity % (Stg1-4)|   |
  |   +-------------------+-------------------+      +---------------------+---------------------+   |
  |                       |                                                |                         |
  |                       +-----------------------+------------------------+                         |
  |                                               |                                                  |
  |                                               v                                                  |
  |   +------------------------------------------------------------------------------------------+   |
  |   |                    C. MULTI-FACTOR DETERMINISTIC HEALTH ENGINE (0 - 100%)                |   |
  |   |      Overall Health Index = 0.30(Pest) + 0.35(Disease) + 0.20(ExG/NDRE) + 0.15(CRI)      |   |
  |   +-------------------------------------------+----------------------------------------------+   |
  |                                               |                                                  |
  |   +---------------------------------------+   |  +-------------------------------------------+   |
  |   |   D. PRECISION DOSAGE CALCULATOR      |   |  |     E. WEATHER RISK & EPIDEMIOLOGY        |   |
  |   |  - Chemical Vol (ml/g) by Acreage     |<--+->|  - Spore Germination Microclimate Radar   |   |
  |   |  - Sprayer Tank Mix Refills (e.g. 16L)|      |  - Fungal / Bacterial / Pest Outbreak Risk|   |
  |   |  - Organic Remedies (Neem/Bio-Agents) |      |  - Optimal Spray Timing Windows (Rain/Wind|   |
  |   +---------------------------------------+      +-------------------------------------------+   |
  +-------------------------------------------------+------------------------------------------------+
                                                    |
                                                    v
  +--------------------------------------------------------------------------------------------------+
  |                               3. ADVISORY, ACTUATION & USER INTERACTION                          |
  |                                                                                                  |
  |  [Multilingual AI Agronomist]       [Hardware Relays Actuation]      [Reports & Dashboard]       |
  |   - 10 Indian Regional Languages     - 5V/12V Solenoid Drip Valves    - React 18 Farm-Gate Kiosk  |
  |   - Voice & Text Chatbot Interface   - Automatic Spray Mist Pumps     - Instant PDF & DOCX Export |
  +--------------------------------------------------------------------------------------------------+
========================================================================================================"""

    r_diag = p_arch.add_run(diagram_text)
    r_diag.font.name = 'Courier New'
    r_diag.font.size = Pt(6.5)
    r_diag.font.color.rgb = PRIMARY_COLOR

    add_body_p(
        "Workflow Description: (1) Soil sensors and microclimate probes capture real-time physiological metrics, while the Raspberry Pi camera captures leaf macro photos. (2) Raw sensor signals are ingested by the Raspberry Pi over RS485/GPIO. (3) Images pass through PyTorch deep learning models for pest and disease classification, alongside ExG/CRI spectral analysis and HSV/LAB lesion segmentation. (4) The Health Engine synthesizes a 0–100% health score. (5) The system computes exact precision tank mix dosages, checks weather risk, and triggers automated drip/spray relays if necessary. (6) Results are presented to the farmer via a 10-language touch kiosk and downloadable PDF/DOCX reports."
    )

    # -------------------------------------------------------------
    # 6. SYSTEM REQUIREMENTS
    # -------------------------------------------------------------
    add_heading_1("6. System Requirements")
    add_body_p("The hardware and software specifications required to deploy and operate AGROBOTAI are detailed below:")

    add_heading_2("A. Hardware Requirements")

    hw_table = doc.add_table(rows=1, cols=4)
    hw_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    hw_hdr = hw_table.rows[0].cells
    hw_hdr[0].text = "Component / Module"
    hw_hdr[1].text = "Specification / Model"
    hw_hdr[2].text = "Interface / Protocol"
    hw_hdr[3].text = "Primary Function in AGROBOTAI"

    for c in hw_hdr:
        set_cell_shading(c, "1B4D3E")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE
        p.runs[0].font.size = Pt(9.5)

    hw_data = [
        ("Master Edge Brain", "Raspberry Pi 4B (4GB/8GB) or Raspberry Pi 5", "USB / GPIO / Ethernet / Wi-Fi", "Hosts local deep learning models, FastAPI backend, SQLite, and React UI offline."),
        ("High-Res Camera", "Raspberry Pi Camera Module 3 (12MP Autofocus)", "15-pin MIPI CSI ribbon", "High-definition macro imaging of leaf veins, pests, and lesion spots."),
        ("Soil NPK Sensor", "RS485 Modbus Industrial 7-in-1 Soil Sensor", "RS485 via MAX485 TTL transceiver", "Continuous real-time measurement of Nitrogen, Phosphorus, Potassium, pH, EC, Temp, Moisture."),
        ("Soil pH Sensor", "Integrated Glass Electrode / RS485 Soil Probe", "RS485 Modbus RTU", "Measures soil acidity/alkalinity (pH 3–9) to diagnose nutrient absorption lockout."),
        ("Ambient Climate", "DHT22 / SHT31 Temperature & Humidity Sensor", "Single-bus Digital GPIO", "Monitors ambient air temperature and relative humidity for disease risk prediction."),
        ("Soil Moisture", "Capacitive Soil Moisture Sensor v1.2", "Analog-to-Digital (ADS1115) / GPIO", "Corrosion-resistant measurement of volumetric water content in root zones."),
        ("Solar Pest Trap", "395nm UV LED Strip + ESP32-CAM Node", "Wi-Fi / 4G LTE SIM7600", "Attracts nocturnal pests, captures trap images, and feeds pest classifier."),
        ("Relay Controller", "5V/12V 2-Channel Optocoupler Relay Module", "GPIO Digital Output", "Controls solenoid drip valves and pesticide misting pump actuation."),
        ("Power Subsystem", "10W Monocrystalline Solar Panel + TP4056 + 18650 Li-ion", "Micro-USB / 5V Step-Down Buck", "Ensures autonomous off-grid field operation with 24-hour battery backup.")
    ]

    for item in hw_data:
        row = hw_table.add_row()
        for idx, text in enumerate(item):
            cell = row.cells[idx]
            set_cell_margins(cell, 60, 60, 80, 80)
            if idx == 0:
                set_cell_shading(cell, "F1F8E9")
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.size = Pt(8.5)
            run.font.name = 'Calibri'
            if idx == 0:
                run.font.bold = True

    add_heading_2("B. Software Requirements")

    sw_table = doc.add_table(rows=1, cols=3)
    sw_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    sw_hdr = sw_table.rows[0].cells
    sw_hdr[0].text = "Software Layer / Tool"
    sw_hdr[1].text = "Version / Technology"
    sw_hdr[2].text = "Role in AGROBOTAI"

    for c in sw_hdr:
        set_cell_shading(c, "1B4D3E")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE
        p.runs[0].font.size = Pt(9.5)

    sw_data = [
        ("Operating System", "Raspberry Pi OS (64-bit Debian) / Windows 11 / Linux", "Host environment for local edge execution and sensor interfacing."),
        ("Programming Language", "Python 3.12+ & JavaScript (ES6+)", "Core language for backend AI pipeline, mathematical engine, and frontend."),
        ("Deep Learning Framework", "PyTorch 2.0+, Torchvision, ONNX Runtime", "Model inference, transfer learning architectures, and GPU/CPU acceleration."),
        ("Computer Vision & Math", "OpenCV (cv2), NumPy, SciPy, PIL, Scikit-Image", "Image preprocessing, HSV/LAB color space segmentation, ExG/CRI spectral math."),
        ("Backend Framework", "FastAPI, Uvicorn, Pydantic", "High-performance async REST API providing endpoints for analysis, dosage, and weather."),
        ("Database Engine", "SQLite3 with SQLAlchemy / Direct SQL", "Lightweight, zero-configuration local database for sensor telemetry and logs."),
        ("Frontend Framework", "React 18, Vite, Tailwind CSS, Lucide Icons", "Responsive SPA with interactive sliders, gauge charts, and webcam capture."),
        ("Natural Language Engine", "Multilingual LLM Engine / Rule-based agronomist", "Conversational AI support in 10 Indian languages with audio/speech synthesis."),
        ("Document Generation", "python-docx (DOCX) & ReportLab (PDF)", "Automated generation of downloadable diagnostic farm health reports.")
    ]

    for item in sw_data:
        row = sw_table.add_row()
        for idx, text in enumerate(item):
            cell = row.cells[idx]
            set_cell_margins(cell, 60, 60, 80, 80)
            if idx == 0:
                set_cell_shading(cell, "F1F8E9")
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.size = Pt(8.5)
            run.font.name = 'Calibri'
            if idx == 0:
                run.font.bold = True

    # -------------------------------------------------------------
    # 7. LIST OF MODULES
    # -------------------------------------------------------------
    add_heading_1("7. List of Modules (Comprehensive Functional Breakdown)")
    add_body_p(
        "AGROBOTAI is organized into 11 functional modules designed for high reliability, modularity, and real-time execution:"
    )

    modules = [
        (
            "Module 1: Edge Computing & Master Gateway Module",
            "Hardware/Software integration on Raspberry Pi 4B/5 that orchestrates local model execution, offline web serving, local telemetry aggregation, and direct hardware GPIO relay actuation without needing cloud connectivity."
        ),
        (
            "Module 2: Multi-Sensor IoT & Telemetry Ingestion Module",
            "Manages RS485 Modbus RTU communication with the 7-in-1 soil probe (Nitrogen, Phosphorus, Potassium, pH, Salinity, Moisture, Temp) and digital GPIO communication with DHT22 sensors, storing real-time readings in the SQLite database."
        ),
        (
            "Module 3: Dual Deep Learning Vision Engine (Pest & Disease Classifier)",
            "PyTorch deep neural network module deploying EfficientNet-B0 and ConvNeXt architectures. Includes a 9-class agricultural pest detector, a 15-class crop disease classifier (PlantVillage), and Grad-CAM visual heatmaps for diagnostic transparency."
        ),
        (
            "Module 4: Bio-Physical Spectral & Biochemical Proxy Module (Chlorophyll & CRI)",
            "Calculates the Excess Green Index (ExG = 2G - R - B) to measure relative active chlorophyll density and canopy greenness. Computes Carotenoid Reflectance Indices (CRI1 = 1/B - 1/G, CRI2 = 1/B - 1/R) to detect pre-symptomatic cellular stress before visible lesions appear."
        ),
        (
            "Module 5: Dual-Space Lesion Segmentation & Severity Grading Module",
            "Performs semantic leaf surface segmentation across dual HSV and LAB color spaces to isolate chlorotic (yellow) and necrotic (brown/black) tissues. Computes exact percentage surface damage and classifies disease severity into Stage 1 (Mild) to Stage 4 (Critical)."
        ),
        (
            "Module 6: Soil & Foliar Nutrient Deficiency Diagnostic Module",
            "Correlates RS485 soil sensor NPK and pH readings with computer vision leaf chlorosis patterns to detect primary (Nitrogen, Phosphorus, Potassium) and micronutrient (Iron, Zinc, Magnesium) deficiencies, identifying soil nutrient lockout."
        ),
        (
            "Module 7: Precision Chemical & Organic Dosage Calculator Module",
            "Dynamic agronomic engine that calculates required chemical volumes (ml or g), water dilution volume, and knapsack sprayer tank refills based on farmer-specified acreage and sprayer capacity. Recommends organic alternatives (Neem oil, Trichoderma) and enforces Pre-Harvest Intervals (PHI)."
        ),
        (
            "Module 8: Microclimate Weather Risk & Epidemiological Forecasting Module",
            "Analyzes ambient temperature, relative humidity, and rainfall forecasts to calculate real-time disease outbreak risks (fungal sporulation, bacterial proliferation, pest population spikes) and recommends optimal spray weather windows."
        ),
        (
            "Module 9: Multilingual AI Agronomist Chatbot Module",
            "Conversational advisory assistant capable of conversing in 10 regional Indian languages (English, Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi), answering farmer queries on remedies, fertilizers, and crop cycles."
        ),
        (
            "Module 10: Automated Actuation & Relay Control Module",
            "Controls 5V/12V optocoupler relays connected to Raspberry Pi GPIOs to automatically switch solenoid drip irrigation valves and micro-sprayer pumps when soil moisture drops below threshold or targeted pesticide misting is scheduled."
        ),
        (
            "Module 11: Farm-Gate Interactive UI & Diagnostic Reporting Module",
            "Modern single-page React 18 dashboard optimized for touch displays and mobile screens. Features live webcam scanning, interactive dosage sliders, risk radars, circular health gauges, and instant export to professional PDF and DOCX reports."
        )
    ]

    for mod_title, mod_desc in modules:
        add_heading_2(mod_title)
        add_body_p(mod_desc)

    # -------------------------------------------------------------
    # 8. DETAILED BREAKDOWN OF NEW & ADVANCED FEATURES
    # -------------------------------------------------------------
    add_heading_1("8. Detailed Breakdown of New & Advanced Features")
    add_body_p(
        "To elevate AGROBOTAI above traditional leaf-disease classification tools, several state-of-the-art engineering modules have been built into the system. Below is the detailed breakdown of each new feature:"
    )

    add_heading_2("Feature 1: Automatic Leaf Species Classifier (src/leaf_classifier.py)")
    add_body_p(
        "Automatically identifies the botanical plant species before diagnosing diseases, eliminating the need for farmers to manually select their crop from dropdowns. Supports 16+ agricultural species including Tomato, Potato, Bell Pepper, Green Chilli, Brinjal, Corn, Rice, Wheat, Cotton, Sugarcane, Soybean, Mango, Banana, Coconut, Tea, and Coffee with high confidence."
    )

    add_heading_2("Feature 2: Multilingual AI Agronomist Chatbot with Regional Focus (src/multilingual_chatbot.py)")
    add_body_p(
        "A context-aware conversational agent supporting 10 Indian languages (Tamil, Hindi, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, and English). Tailored with deep Tamil localized agricultural vocabulary. When a scan detects Early Blight on Tomato, the chatbot automatically adopts that context, answering questions on chemical dosage, organic remedies, irrigation, and recovery schedules."
    )

    add_heading_2("Feature 3: Quantitative Dual-Space Lesion Severity Segmentation (src/disease_severity.py)")
    add_body_p(
        "Utilizes dual HSV and LAB color spaces to semantically segment leaf photos into healthy green canopy, chlorotic tissue (yellow), and necrotic lesions (brown/black). It computes exact surface damage percentage and categorizes severity into 4 actionable stages: Stage 1 (<10% Mild), Stage 2 (10-25% Moderate), Stage 3 (25-50% High), and Stage 4 (>50% Critical)."
    )

    add_heading_2("Feature 4: Soil & Foliar Nutrient Deficiency Engine (src/nutrient_deficiency.py)")
    add_body_p(
        "Analyzes both soil sensor readings (NPK, pH) and foliar visual patterns to diagnose 6 key deficiencies: Nitrogen (N), Phosphorus (P), Potassium (K), Iron (Fe), Zinc (Zn), and Magnesium (Mg). It identifies nutrient lockout conditions caused by improper soil pH (e.g., pH > 7.5 causing Iron/Zinc lockout even if present in soil)."
    )

    add_heading_2("Feature 5: Dynamic Precision Spray Dosage & Tank Calculator (src/dosage_calculator.py)")
    add_body_p(
        "Eliminates pesticide over-spraying by computing exact dilution math. Farmers adjust live sliders for field acreage (e.g., 2.5 acres) and knapsack sprayer capacity (e.g., 16 Litres). The engine outputs exact chemical volume in ml or grams, total water volume, number of tank refills, organic bio-pesticide alternatives (Neem oil, Trichoderma viride), and Pre-Harvest Intervals (PHI)."
    )

    add_heading_2("Feature 6: Microclimate Weather Disease Risk Radar (src/weather_forecast.py)")
    add_body_p(
        "Combines live temperature, relative humidity, and rainfall forecasts to run an epidemiological risk model. It alerts farmers to fungal spore germination conditions (Humidity > 85%, Temp 20-28°C), bacterial blight proliferation, and warns against spraying during high wind or imminent rain."
    )

    add_heading_2("Feature 7: Crop Recovery Progress Tracker (src/recovery_tracker.py)")
    add_body_p(
        "Enables periodic multi-scan monitoring of the same plant at 7, 14, and 21 days. Plots historical 0-100% health score trends over time to empirically verify whether applied treatments or fertilizers are successfully curing the crop."
    )

    add_heading_2("Feature 8: Explainable AI with Grad-CAM Heatmaps (src/gradcam_viz.py)")
    add_body_p(
        "Generates visual Grad-CAM gradient heatmaps superimposed onto the input leaf image, highlighting the exact pixels and features responsible for the neural network's diagnosis, fostering trust and transparency for agricultural scientists."
    )

    add_heading_2("Feature 9: Raspberry Pi Edge Hub & Multi-Sensor Hardware Integration")
    add_body_p(
        "Seamless integration with Raspberry Pi 4B/5, Raspberry Pi Camera Module 3, RS485 Modbus 7-in-1 Soil NPK/pH probes, DHT22 sensors, 395nm solar UV insect traps, and GPIO dual-channel relays, delivering 100% offline edge AI execution."
    )

    # Comparison Table
    add_heading_2("Feature Comparison: Traditional Systems vs. AGROBOTAI")

    comp_table = doc.add_table(rows=1, cols=3)
    comp_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    c_hdr = comp_table.rows[0].cells
    c_hdr[0].text = "Feature / Capability"
    c_hdr[1].text = "Traditional / Earlier Systems"
    c_hdr[2].text = "AGROBOTAI Platform (New)"

    for c in c_hdr:
        set_cell_shading(c, "1B4D3E")
        set_cell_margins(c, 80, 80, 100, 100)
        p = c.paragraphs[0]
        p.runs[0].font.bold = True
        p.runs[0].font.color.rgb = WHITE
        p.runs[0].font.size = Pt(9.5)

    comp_data = [
        ("Crop Identification", "Manual selection from dropdown list.", "Automatic detection of 16+ leaf species."),
        ("Language Accessibility", "English only or standard Hindi.", "10 Indian regional languages (Tamil focus, etc.)."),
        ("Disease Severity", "Categorical disease name only.", "Dual-space HSV/LAB Stage 1-4 damage %."),
        ("Nutrient Deficiency", "None / Manual lab testing.", "6-Element Soil & Foliar Diagnostic Engine (N, P, K, Fe, Zn, Mg)."),
        ("Chemical Spray Advisory", "Static dosage text guidelines.", "Dynamic tank mix calculator based on acreage & tank liters."),
        ("Disease Outbreak Risk", "None.", "Epidemiological microclimate weather risk radar."),
        ("Explainable AI", "Black-box predictions.", "Grad-CAM visual attention heatmaps."),
        ("Edge Computing", "Cloud-only dependent.", "100% Offline Edge AI on Raspberry Pi + Multi-Sensor IoT.")
    ]

    for item in comp_data:
        row = comp_table.add_row()
        for idx, text in enumerate(item):
            cell = row.cells[idx]
            set_cell_margins(cell, 60, 60, 80, 80)
            if idx == 0:
                set_cell_shading(cell, "F1F8E9")
            p = cell.paragraphs[0]
            run = p.add_run(text)
            run.font.size = Pt(8.5)
            run.font.name = 'Calibri'
            if idx == 0:
                run.font.bold = True

    # -------------------------------------------------------------
    # 9. CONCLUSION & FUTURE SCOPE
    # -------------------------------------------------------------
    add_heading_1("9. Conclusion & Future Scope")
    add_body_p(
        "AGROBOTAI establishes a robust, highly accessible, and scientific precision agriculture platform that bridges the gap between laboratory research and real-world farm fields. By integrating Raspberry Pi edge computing, multi-spectral optical proxies (ExG, CRI), multi-sensor soil telemetry (NPK, pH, temperature, moisture), deep learning vision models (Pests & Diseases), precision chemical/organic dosage calculations, and 10-language regional conversational assistance, AGROBOTAI equips smallholder farmers with actionable, localized intelligence. Future work includes integrating drone multispectral cameras for large-scale canopy scanning, LoRaWAN mesh networking for multi-acre node communication, and satellite remote-sensing data fusion."
    )

    # Save document
    filename = "AGROBOTAI_Project_Documentation.docx"
    try:
        doc.save(filename)
        print(f"Document successfully created: {filename}")
    except PermissionError:
        alt_filename = "AGROBOTAI_Master_Project_Documentation.docx"
        doc.save(alt_filename)
        print(f"Primary file '{filename}' was locked (open in Word). Saved successfully as: {alt_filename}")

if __name__ == "__main__":
    create_document()
