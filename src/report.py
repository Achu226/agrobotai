from __future__ import annotations

from datetime import datetime
from io import BytesIO


def _line(label: str, value) -> str:
    return f"{label}: {value if value is not None else 'N/A'}"


def build_text_report(result: dict) -> str:
    pest = result.get("pest") or {}
    disease = result.get("disease") or {}
    ndre = result.get("ndre") or {}
    cri = result.get("cri") or {}
    overall = result.get("overall") or {}
    advice = result.get("advice") or {}

    lines = [
        "AI CROP HEALTH ADVISOR REPORT",
        "=" * 40,
        _line("Generated", result.get("timestamp") or datetime.now().isoformat(timespec="seconds")),
        _line("Crop", result.get("crop")),
        "",
        "OVERALL HEALTH",
        _line("Score", f"{overall.get('overall_score')}/100" if overall.get("overall_score") is not None else "N/A"),
        _line("Status", overall.get("overall_status")),
        _line("Assessment Confidence", overall.get("assessment_confidence")),
        "",
        "PEST DETECTION",
        _line("Result", pest.get("display_name")),
        _line("Confidence", f"{pest.get('confidence')}%" if pest.get("confidence") is not None else pest.get("error")),
        _line("Score", pest.get("score")),
        _line("Status", pest.get("status")),
        "",
        "LEAF DISEASE",
        _line("Result", disease.get("display_name")),
        _line("Confidence", f"{disease.get('confidence')}%" if disease.get("confidence") is not None else disease.get("error")),
        _line("Score", disease.get("score")),
        _line("Status", disease.get("status")),
        "",
        "NDRE / CHLOROPHYLL (RGB proxy)",
        _line("Value", ndre.get("value")),
        _line("Status", ndre.get("status")),
        _line("Score", ndre.get("score")),
        "",
        "CRI / CAROTENOID (RGB proxy)",
        _line("Value", cri.get("value")),
        _line("Status", cri.get("status")),
        _line("Score", cri.get("score")),
        "",
        "SPECTRAL LIMITATION",
        result.get("spectral_limitation") or "",
        "",
        "AI FARMER ADVISOR",
    ]

    sections = [
        ("IMMEDIATE ACTIONS", "immediate_actions"),
        ("NEXT 24-48 HOURS", "next_24_48_hours"),
        ("NEXT 7 DAYS", "next_7_days"),
        ("PREVENTION", "prevention"),
        ("PEST MANAGEMENT", "pest_management"),
        ("DISEASE MANAGEMENT", "disease_management"),
        ("IRRIGATION", "irrigation"),
        ("NUTRIENTS", "nutrients"),
        ("FIELD MONITORING", "field_monitoring"),
        ("YIELD", "yield_notes"),
        ("WARNINGS", "warnings"),
    ]
    for title, key in sections:
        lines.append("")
        lines.append(title)
        items = advice.get(key) or []
        if not items:
            lines.append("- None")
        else:
            for item in items:
                lines.append(f"- {item}")

    failed = result.get("failed_modules") or []
    if failed:
        lines.append("")
        lines.append("FAILED MODULES")
        for item in failed:
            lines.append(f"- {item.get('module')}: {item.get('error')}")

    return "\n".join(lines)


def build_pdf_report(result: dict) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, title="Crop Health Report")
    styles = getSampleStyleSheet()
    story = []
    for raw_line in build_text_report(result).splitlines():
        line = raw_line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        if not line.strip():
            story.append(Spacer(1, 6))
        elif line.isupper() or line.startswith("AI CROP"):
            story.append(Paragraph(line, styles["Heading2"]))
        else:
            story.append(Paragraph(line, styles["BodyText"]))
    doc.build(story)
    return buffer.getvalue()


def build_docx_report(result: dict) -> bytes:
    from docx import Document
    from docx.shared import Inches, Pt

    doc = Document()
    crop = result.get("crop", "Plant")
    timestamp = result.get("timestamp") or datetime.now().isoformat(timespec="seconds")

    doc.add_heading(f"AI Crop Health & Pigment Analysis Report - {crop}", level=1)
    doc.add_paragraph(f"Timestamp: {timestamp}")

    overall = result.get("overall") or {}
    doc.add_heading("Overall Plant Health", level=2)
    doc.add_paragraph(f"Overall Score: {overall.get('overall_score')}/100")
    doc.add_paragraph(f"Overall Status: {overall.get('overall_status')}")
    doc.add_paragraph(f"Confidence: {overall.get('assessment_confidence')}")

    pest = result.get("pest") or {}
    doc.add_heading("Pest Detection", level=2)
    doc.add_paragraph(f"Identified: {pest.get('display_name')}")
    doc.add_paragraph(f"Confidence: {pest.get('confidence')}%" if pest.get("confidence") is not None else f"Error: {pest.get('error')}")
    doc.add_paragraph(f"Status: {pest.get('status')}")

    disease = result.get("disease") or {}
    doc.add_heading("Leaf Disease Detection", level=2)
    doc.add_paragraph(f"Identified: {disease.get('display_name')}")
    doc.add_paragraph(f"Confidence: {disease.get('confidence')}%" if disease.get("confidence") is not None else f"Error: {disease.get('error')}")
    doc.add_paragraph(f"Status: {disease.get('status')}")

    ndre = result.get("ndre") or {}
    doc.add_heading("Chlorophyll Analysis (ExG NDRE Proxy)", level=2)
    doc.add_paragraph(f"Mean ExG Proxy Value: {ndre.get('value')}")
    doc.add_paragraph(f"Minimum Value: {ndre.get('min')}")
    doc.add_paragraph(f"Maximum Value: {ndre.get('max')}")
    doc.add_paragraph(f"Classification: {ndre.get('class')}")
    doc.add_paragraph(f"Status: {ndre.get('status')}")

    cri = result.get("cri") or {}
    doc.add_heading(f"Carotenoid Analysis ({cri.get('variant', 'CRI1')} Proxy)", level=2)
    doc.add_paragraph(f"Mean Normalized CRI Value: {cri.get('value')}")
    doc.add_paragraph(f"Minimum Value: {cri.get('min')}")
    doc.add_paragraph(f"Maximum Value: {cri.get('max')}")
    doc.add_paragraph(f"Classification: {cri.get('class')}")
    doc.add_paragraph(f"Status: {cri.get('status')}")

    advice = result.get("advice") or {}
    doc.add_heading("AI Agronomic Action Plan", level=2)
    for key, title in [
        ("immediate_actions", "Immediate Urgent Actions"),
        ("next_24_48_hours", "Next 24-48 Hours"),
        ("next_7_days", "Next 7 Days"),
        ("prevention", "Preventive Field Measures"),
        ("pest_management", "Pest Management"),
        ("disease_management", "Disease Control"),
        ("irrigation", "Irrigation Guidance"),
        ("nutrients", "Nutrient Management"),
    ]:
        items = advice.get(key) or []
        if items:
            doc.add_heading(title, level=3)
            for item in items:
                doc.add_paragraph(f"• {item}")

    buffer = BytesIO()
    doc.save(buffer)
    return buffer.getvalue()


def build_scan_pdf(scan: dict, image_path: str | None = None) -> bytes:
    """
    PDF for one stored scan. Built only from the saved record (never re-runs inference), so an old
    report always shows the original result. Fields the scan does not have are printed as
    "Not available" rather than filled in.
    """
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    def esc(v) -> str:
        return str(v).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def val(v, suffix: str = "") -> str:
        return "Not available" if v is None or v == "" else f"{esc(v)}{suffix}"

    result = scan.get("result") or {}
    disease = result.get("disease") or {}
    pest = result.get("pest") or {}
    severity = result.get("severity") or {}
    health = result.get("health_index") or {}
    advice = result.get("advice") or {}
    summary = result.get("summary") or {}

    styles = getSampleStyleSheet()
    buffer = BytesIO()
    # pageCompression=0 keeps the text searchable/verifiable in tests and by auditors
    doc = SimpleDocTemplate(buffer, pagesize=A4, pageCompression=0, title=f"AGROBOTAI scan #{scan['id']}",
                            leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    story = [Paragraph(f"AGROBOTAI Crop Scan Report #{scan['id']}", styles["Title"])]

    def table(rows):
        t = Table([[Paragraph(f"<b>{esc(k)}</b>", styles["BodyText"]), Paragraph(v, styles["BodyText"])] for k, v in rows],
                  colWidths=[5.2 * cm, 11.6 * cm])
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#ecfdf5"))]))
        return t

    story += [table([
        ("Scan ID", f"{scan['id']} ({esc(scan.get('uuid'))})"),
        ("Farmer", val(scan.get("full_name") or scan.get("username"))),
        ("Captured at", val(scan.get("captured_at"))),
        ("Received at", val(scan.get("received_at"))),
        ("Inference status", val(scan.get("inference_status"))),
        ("Overall result", val(summary.get("message"))),
        ("Crop (selected / model)", f"{val(scan.get('crop_selected'))} / {val(scan.get('crop_reported'))}"),
        ("Model versions", val(", ".join(f"{k}: {v}" for k, v in (scan.get("model_versions") or {}).items() if v))),
    ]), Spacer(1, 10)]

    if image_path:
        try:
            story += [RLImage(image_path, width=7 * cm, height=7 * cm, kind="proportional"), Spacer(1, 10)]
        except Exception:  # noqa: BLE001 - a missing image file must not block the report
            story.append(Paragraph("Captured image: not available", styles["BodyText"]))

    story += [Paragraph("Disease classification", styles["Heading2"]), table([
        ("Result", val(disease.get("message"))),
        ("Predicted class", val(disease.get("display_name"))),
        ("Calibrated confidence", val(disease.get("calibrated_confidence"), "%")),
        ("Raw model score", val(disease.get("model_score"), "%")),
        ("State", val(disease.get("state"))),
    ]), Paragraph("Pest classification", styles["Heading2"]), table([
        ("Result", val(pest.get("message"))),
        ("State", val(pest.get("state"))),
        ("Top model guess", val(pest.get("top_prediction"))),
        ("Calibrated confidence", val(pest.get("calibrated_confidence"), "%")),
        ("Localisation", val(pest.get("localization_note"))),
    ]), Paragraph("Severity & health index", styles["Heading2"]), table([
        ("Affected leaf area", val(severity.get("affected_pct"), "%")),
        ("Severity stage", val(severity.get("stage"))),
        ("Heuristic health index", val(health.get("value"), "/100")),
        ("Health index formula", val(health.get("formula"))),
    ])]

    items = [i for k in ("immediate_actions", "next_24_48_hours", "next_7_days", "prevention", "items") for i in (advice.get(k) or [])]
    story.append(Paragraph(f"Advice (source: {val(advice.get('source') or advice.get('state'))})", styles["Heading2"]))
    story += [Paragraph(f"• {esc(i)}", styles["BodyText"]) for i in items] or [Paragraph("Not available", styles["BodyText"])]

    reviewer = scan.get("reviewer_username")
    story += [Paragraph("Administrator review", styles["Heading2"]), table([
        ("Review status", val(scan.get("review_status"))),
        ("Reviewed by", val(reviewer)),
        ("Reviewed at", val(scan.get("reviewed_at"))),
        ("Comment", val(scan.get("review_comment"))),
    ]), Spacer(1, 12), Paragraph(
        "Model outputs are decision support only and cover a limited set of crops, diseases and pests. "
        "Confirm with an agricultural expert before applying chemicals.", styles["Italic"])]
    doc.build(story)
    return buffer.getvalue()
