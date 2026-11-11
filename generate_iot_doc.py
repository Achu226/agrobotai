"""
Generate a professional, fully-styled Word document for HORTICBOTAI IoT Smart Farm System
"""
import os
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn

def set_cell_background(cell, fill_hex):
    tcPr = cell._element.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{fill_hex}"/>')
    tcPr.append(shd)

def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    tcPr = cell._element.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def add_callout(doc, text_title, text_body, bg_hex="E8F5E9", border_hex="2E7D32"):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    set_cell_background(cell, bg_hex)
    set_cell_margins(cell, top=140, bottom=140, left=200, right=200)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    run_t = p.add_run(f"💡 {text_title}\n")
    run_t.bold = True
    run_t.font.size = Pt(11)
    run_t.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)

    run_b = p.add_run(text_body)
    run_b.font.size = Pt(10)
    run_b.font.color.rgb = RGBColor(0x2E, 0x38, 0x2E)

def style_table(table, header_bg="1B5E20", alt_row_bg="F1F8E9"):
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    # Format header row
    for cell in table.rows[0].cells:
        set_cell_background(cell, header_bg)
        set_cell_margins(cell, top=120, bottom=120, left=140, right=140)
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            for r in p.runs:
                r.bold = True
                r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                r.font.size = Pt(10)

    # Format data rows
    for i, row in enumerate(table.rows[1:], start=1):
        bg = alt_row_bg if i % 2 == 0 else "FFFFFF"
        for cell in row.cells:
            set_cell_background(cell, bg)
            set_cell_margins(cell, top=90, bottom=90, left=130, right=130)
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9.5)
                    r.font.color.rgb = RGBColor(0x21, 0x21, 0x21)

def main():
    doc = Document()

    # Configure Margins
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(0.85)
        section.right_margin = Inches(0.85)

    # Document Header
    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(0)
    title_p.paragraph_format.space_after = Pt(4)
    r_title = title_p.add_run("HORTICBOTAI: Closed-Loop IoT & Edge AI Smart Farm Architecture")
    r_title.bold = True
    r_title.font.size = Pt(22)
    r_title.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)

    sub_p = doc.add_paragraph()
    sub_p.paragraph_format.space_after = Pt(16)
    r_sub = sub_p.add_run("Comprehensive Blueprint: Hardware BOM, Patent Novelty Claims, Edge AI Camera Trap, and Q1 Journal Publication Strategy")
    r_sub.italic = True
    r_sub.font.size = Pt(12)
    r_sub.font.color.rgb = RGBColor(0x55, 0x8B, 0x2F)

    # Divider line
    doc.add_paragraph("―" * 58)

    # SECTION 1: EXECUTIVE SUMMARY
    h1 = doc.add_heading("1. Executive Overview & Cyber-Physical Vision", level=1)
    h1.paragraph_format.space_before = Pt(14)

    p = doc.add_paragraph()
    p.add_run(
        "HORTICBOTAI is evolving from a standalone computer vision diagnostic suite into a comprehensive, "
        "closed-loop Cyber-Physical Precision Agriculture System (CP-PAS). By coupling edge-computed optical spectral proxies "
        "(ExG, CRI1, CRI2) with in-situ microclimate and sub-surface physicochemical telemetry (7-in-1 NPK, EC, pH, moisture, leaf wetness), "
        "the system eliminates diagnostic ambiguity and automates targeted variable-rate actuation."
    )

    add_callout(
        doc,
        "System Vision: True Autonomy in Agronomy",
        "Instead of relying on human scouting or manual pump switching, HORTICBOTAI establishes a closed bio-cybernetic loop: "
        "Edge sensors detect stress -> Vision AI isolates pathogens & pests -> The Bio-Physical Engine calculates exact water/chemical requirements -> "
        "Micro-relays trigger solenoid drip zones and anti-fungal misting before irreversible economic crop damage occurs."
    )

    # SECTION 2: PATENT CLAIMS & NOVELTY ANALYSIS
    h2 = doc.add_heading("2. Patent Novelty & Intellectual Property (IP) Strategy", level=1)
    h2.paragraph_format.space_before = Pt(14)

    p = doc.add_paragraph()
    p.add_run(
        "To secure a utility patent and publish in top-tier journals (IEEE IoT-J, Elsevier Computers and Electronics in Agriculture), "
        "the architecture bypasses trivial threshold-based irrigation and focuses on three distinctly novel, patentable mechanisms:"
    )

    claims = [
        ("Claim 1: Optical-Physicochemical Bio-Cross-Validation Engine",
         "A method for disaggregating foliar chlorosis by cross-referencing high-frequency RGB/spectral proxies (ExG Chlorophyll and CRI Carotenoid stress) "
         "against real-time sub-surface electrical conductivity (EC) and NPK ionic availability. The system mathematically distinguishes between "
         "macronutrient starvation, osmotic salt stress, and fungal pathogenesis prior to symptomatic lesion necrosis."),

        ("Claim 2: Dynamic Economic Injury Level (EIL) Edge Camera Trap",
         "A solar-powered autonomous edge-vision trap utilizing dual-spectrum (daylight RGB + 395nm UV nocturnal) illumination and quantized neural networks "
         "(YOLOv8-Nano / NCNN) running on a Raspberry Pi. Rather than simple pest counting, it dynamically calculates real-time Economic Thresholds (ET) "
         "based on crop phenological stage and microclimate trajectories to trigger micro-dosed bio-pesticide misting."),

        ("Claim 3: Leaf Wetness Duration (LWD) Pathogen Preemption Loop",
         "A closed-loop preventative actuation method utilizing dielectric leaf wetness sensors, ambient vapor pressure deficit (VPD), and temperature trends. "
         "When continuous leaf wetness exceeds crop-specific spore germination thresholds (e.g., Phytophthora infestans 6-hour wet window), the system automatically "
         "pulses anti-humidity canopy ventilation or prophylactic bio-fungicide fogging.")
    ]

    for title, desc in claims:
        cp = doc.add_paragraph()
        cp.paragraph_format.space_before = Pt(6)
        cp.paragraph_format.space_after = Pt(4)
        run_t = cp.add_run(f"📌 {title}\n")
        run_t.bold = True
        run_t.font.color.rgb = RGBColor(0x2E, 0x7D, 0x32)
        cp.add_run(desc)

    # SECTION 3: THREE-TIER HARDWARE ARCHITECTURE
    h3 = doc.add_heading("3. Hardware Architecture & Node Topology", level=1)
    h3.paragraph_format.space_before = Pt(14)

    p = doc.add_paragraph()
    p.add_run("The physical deployment is structured into three interconnected functional nodes:")

    nodes_info = [
        ("Node A: Edge AI Camera Trap & Gateway (Raspberry Pi 4/5)", [
            "Processor: Broadcom BCM2711 Quad-Core Cortex-A72 @ 1.8GHz (Pi 4 4GB/8GB) or Pi 5.",
            "Optical Sensor: Raspberry Pi Camera Module 3 (Sony IMX708 12MP, Autofocus, HDR).",
            "Spectral Attraction: 395nm UV LED Array (night nocturnal insect attraction) + 850nm IR illuminator.",
            "Edge Runtime: ONNX Runtime / NCNN with INT8 quantized YOLOv8-Nano pest detection engine.",
            "Field Communication: Local Wi-Fi Gateway / 4G LTE HAT (SIM7600) for telemetry forwarding."
        ]),
        ("Node B: Multi-Parametric In-Ground & Canopy Node (ESP32-S3)", [
            "Microcontroller: ESP32-WROOM-32D / ESP32-S3 with ultra-low power Deep Sleep (<15uA).",
            "Sub-Surface Probe: Industrial RS485 Modbus 7-in-1 Soil Sensor (N, P, K, pH, Moisture, Temp, EC).",
            "Bus Interface: MAX485 TTL-to-RS485 transceiver with ESD protection.",
            "Canopy Instrumentation: Dielectric Leaf Wetness Grid Plate + SHT31 Digital Temp/RH Sensor."
        ]),
        ("Node C: Variable-Rate Precision Actuation Unit (Relay & Hydraulics)", [
            "Controller: 4-Channel 5V Optocoupler-Isolated Solid State / Mechanical Relay Module.",
            "Pumping System: 12V DC High-Pressure Diaphragm Water Pump (4.5 L/min, 0.6 MPa).",
            "Zone Solenoids: 12V 1/2-inch Normally Closed Solenoids (Zone 1: Root Drip, Zone 2: Foliar Mist).",
            "Distribution: Food-grade UV-resistant LDPE drip lines with pressure-compensating micro-emitters."
        ])
    ]

    for node_name, points in nodes_info:
        np = doc.add_paragraph()
        np.paragraph_format.space_before = Pt(6)
        r = np.add_run(f"🔹 {node_name}")
        r.bold = True
        r.font.color.rgb = RGBColor(0x1B, 0x5E, 0x20)
        for pt in points:
            doc.add_paragraph(f"  • {pt}", style='List Bullet')

    # SECTION 4: BILL OF MATERIALS & COSTING TABLE
    h4 = doc.add_heading("4. Comprehensive Bill of Materials (BOM) & Cost Breakdown", level=1)
    h4.paragraph_format.space_before = Pt(14)

    p = doc.add_paragraph()
    p.add_run("The component budget is categorized into three deployment tiers to match research, lab prototyping, or field scale:")

    # Summary Table
    t_summary = doc.add_table(rows=4, cols=4)
    t_summary.rows[0].cells[0].paragraphs[0].text = "Tier Level"
    t_summary.rows[0].cells[1].paragraphs[0].text = "Target Purpose"
    t_summary.rows[0].cells[2].paragraphs[0].text = "Cost (INR ₹)"
    t_summary.rows[0].cells[3].paragraphs[0].text = "Cost (USD $)"

    summary_data = [
        ("Tier 1: Lab Prototype", "Lab verification, college demo, benchtop testing", "₹7,500 – ₹10,500", "$90 – $125"),
        ("Tier 2: Research & Patent Grade", "Published Q1 paper, working field prototype, IP filing", "₹18,500 – ₹24,000", "$220 – $290"),
        ("Tier 3: Commercial Solar Off-Grid", "24/7 autonomous 1-acre farm deployment", "₹32,000 – ₹42,000", "$380 – $500")
    ]

    for i, row in enumerate(summary_data, start=1):
        for j, val in enumerate(row):
            t_summary.rows[i].cells[j].paragraphs[0].text = val
    style_table(t_summary, header_bg="2E7D32", alt_row_bg="E8F5E9")

    doc.add_paragraph() # Spacing

    # Detailed Itemized Table
    doc.add_heading("Detailed Itemized Component Breakdown", level=2)
    bom_items = [
        ("Raspberry Pi 4 Model B (4GB RAM)", "Edge AI inference gateway", "1 Unit", "₹5,500", "$65"),
        ("Raspberry Pi Camera Module 3 (Wide HDR)", "12MP autofocus crop & pest capture", "1 Unit", "₹2,300", "$28"),
        ("395nm UV LED Array + 850nm IR Ring", "Nocturnal insect attraction & vision", "1 Set", "₹450", "$5.50"),
        ("ESP32 Dev Board (ESP-WROOM-32)", "Sensor telemetry microcontroller", "1 Unit", "₹350", "$4.20"),
        ("7-in-1 RS485 Industrial Soil Sensor", "Measures N, P, K, pH, EC, Temp, Moisture", "1 Unit", "₹4,800", "$58"),
        ("MAX485 TTL-to-RS485 Transceiver", "Modbus serial communication bridge", "1 Unit", "₹50", "$0.60"),
        ("Dielectric Leaf Wetness Sensor Plate", "Spore germination surface wetness check", "1 Unit", "₹550", "$6.50"),
        ("SHT31 / BME280 Digital Sensor", "Precision ambient microclimate temp & RH", "1 Unit", "₹380", "$4.50"),
        ("4-Channel 5V Optocoupler Relay", "Pump and solenoid valve switching", "1 Unit", "₹180", "$2.20"),
        ("12V DC Diaphragm Water Pump (0.6MPa)", "High-pressure drip & mist feed", "1 Unit", "₹680", "$8.20"),
        ("12V 1/2-inch Solenoid Valves", "Dual-zone automated valve control", "2 Units", "₹800", "$9.60"),
        ("Drip Line + Micro-Misting Nozzles Kit", "Fluid delivery & canopy misting", "10m Kit", "₹500", "$6.00"),
        ("12V 25W Solar Panel + Solar Charge Controller", "Off-grid power generation & regulation", "1 Set", "₹2,200", "$26.50"),
        ("12V 9Ah Sealed Battery / LiFePO4", "24-48 hr continuous off-grid buffer", "1 Unit", "₹1,400", "$17"),
        ("IP65 Weatherproof Enclosures & Cables", "Outdoor moisture & dust protection", "2 Units", "₹750", "$9")
    ]

    t_bom = doc.add_table(rows=len(bom_items)+1, cols=5)
    t_bom.rows[0].cells[0].paragraphs[0].text = "Component Name"
    t_bom.rows[0].cells[1].paragraphs[0].text = "Specification / Function"
    t_bom.rows[0].cells[2].paragraphs[0].text = "Qty"
    t_bom.rows[0].cells[3].paragraphs[0].text = "INR (₹)"
    t_bom.rows[0].cells[4].paragraphs[0].text = "USD ($)"

    for i, item in enumerate(bom_items, start=1):
        for j, val in enumerate(item):
            t_bom.rows[i].cells[j].paragraphs[0].text = val
    style_table(t_bom, header_bg="1B5E20", alt_row_bg="F1F8E9")

    # SECTION 5: SOFTWARE & CLOSED-LOOP ALGORITHMS
    h5 = doc.add_heading("5. Software Integration & Cyber-Physical Pipeline", level=1)
    h5.paragraph_format.space_before = Pt(14)

    doc.add_paragraph(
        "The software architecture establishes seamless synchronization between the hardware nodes and the HORTICBOTAI server:"
    )

    steps = [
        ("1. ESP32 Sensor Telemetry Ingestion",
         "The ESP32 reads RS485 Modbus registers every 60 seconds, polls SHT31 over I2C, and samples the analog leaf wetness grid. "
         "It formats the payload as JSON and posts to FastAPI `/api/iot/telemetry` or MQTT topic `horticbot/telemetry` before entering low-power sleep."),

        ("2. Raspberry Pi Edge Vision & Trap Synchronization",
         "A background daemon (`edge/rpi_camera_trap.py`) controls the 395nm UV light schedule (active 19:00 - 05:00). When pests gather, the Pi captures "
         "high-resolution frames, runs quantized YOLOv8-Nano inference, calculates local pest density, and transmits alerts to the server."),

        ("3. Server-Side Bio-Physical Fusion Engine (`src/iot_engine.py`)",
         "Combines optical indices (ExG chlorophyll, CRI carotenoids, HSV severity) with soil NPK and moisture. "
         "If leaf chlorosis is high but soil nitrogen is adequate, the engine flags vascular pathogen blockage rather than soil nutrient deficiency."),

        ("4. Autonomous Actuation Controller (`src/iot_actuator.py`)",
         "Evaluates Crop Water Stress Index (CWSI) and Leaf Wetness Duration (LWD). Triggers relay channels via REST or MQTT: "
         "Relay 1 (Drip Pump) when soil moisture < 35%, Relay 2 (Anti-fungal misting) when humidity & spore risk peak.")
    ]

    for st, sd in steps:
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(4)
        r = p.add_run(f"⚙️ {st}\n")
        r.bold = True
        r.font.color.rgb = RGBColor(0x2E, 0x7D, 0x32)
        p.add_run(sd)

    # SECTION 6: RESEARCH PUBLICATION ROADMAP
    h6 = doc.add_heading("6. Q1 Journal Publication & Experimental Roadmap", level=1)
    h6.paragraph_format.space_before = Pt(14)

    doc.add_paragraph(
        "To publish a high-impact paper in top-tier SCI/Scopus Q1 journals, follow this structured experimental setup:"
    )

    journals = [
        ("Computers and Electronics in Agriculture (Elsevier)", "Impact Factor: 7.7 | Focus: Closed-loop smart farming, AI sensor fusion"),
        ("IEEE Internet of Things Journal (IEEE)", "Impact Factor: 10.6 | Focus: Cyber-physical edge computing, low-power IoT architectures"),
        ("Smart Agricultural Technology (Elsevier)", "Impact Factor: 5.8 | Focus: Practical precision agriculture & sensor instrumentation")
    ]

    for jn, desc in journals:
        jp = doc.add_paragraph(style='List Bullet')
        r = jp.add_run(f"{jn}: ")
        r.bold = True
        jp.add_run(desc)

    doc.add_heading("Key Experimental Metrics to Collect for the Paper", level=2)
    metrics = [
        "Diagnostic Accuracy: Confusion matrix and F1-score comparing vision-only vs. fused IoT+Vision diagnosis.",
        "Water Conservation: Percentage water saved using CWSI-driven smart drip vs. traditional timer-based irrigation (typically 25% - 40% reduction).",
        "Disease Preemption Rate: Reduction in disease lesion severity by triggering pre-symptomatic misting based on Leaf Wetness Duration.",
        "Edge Latency & Power: Quantized YOLOv8 inference time on Raspberry Pi (FPS) and battery longevity under solar sleep cycles."
    ]
    for m in metrics:
        doc.add_paragraph(f"  📊 {m}", style='List Bullet')

    # Save document
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "HORTICBOTAI_IoT_Smart_Farm_Patent_and_Features_Blueprint.docx")
    doc.save(out_path)
    print(f"[SUCCESS] Document generated successfully at: {out_path}")

if __name__ == "__main__":
    main()
