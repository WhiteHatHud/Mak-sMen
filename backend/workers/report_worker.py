# workers/report_worker.py
from __future__ import annotations
from typing import Dict, Any, List, Optional
import os
import io
import json
import base64
import zipfile
import logging
from datetime import datetime, timezone

from celery import Celery

from services.llm.report_generator import ReportGenerator
from services.llm.explainer import ExplainerService

import matplotlib
matplotlib.use("Agg") # headless
import matplotlib.pyplot as plt

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as pdf_canvas
from reportlab.lib.utils import ImageReader

# Reuse Celery instance
report_app = celery_app
logger = logging.getLogger(__name__)


REPORT_DIR = os.getenv("REPORT_DIR", os.path.join(os.getcwd(), "reports"))
os.makedirs(REPORT_DIR, exist_ok=True)


# Access analysis cache from analysis worker
get_cached_results = globals().get("get_cached_results") # type: ignore


def _make_charts(summary: Dict[str, Any], anomalies: List[Dict[str, Any]]) -> Dict[str, str]:
    paths: Dict[str, str] = {}
    # Histogram of anomaly probabilities
    probs = [a["prob"] for a in anomalies]
    fig1 = plt.figure()
    plt.hist(probs, bins=20)
    plt.title("Anomaly Probability Distribution")
    plt.xlabel("Probability")
    plt.ylabel("Count")
    p1 = os.path.join(REPORT_DIR, f"{summary['analysis_id']}_hist.png")
    fig1.savefig(p1, bbox_inches='tight')
    plt.close(fig1)

    # Feature importance (if available from first anomaly)
    fi = anomalies[0].get("feature_importance", {}) if anomalies else {}
    if fi:
        names = list(fi.keys())[:15]
        vals = [fi[n] for n in names]
        fig2 = plt.figure()
        plt.barh(names, vals)
        plt.title("Feature Importance")
        plt.xlabel("Importance")
        p2 = os.path.join(REPORT_DIR, f"{summary['analysis_id']}_fi.png")
        fig2.savefig(p2, bbox_inches='tight')
        plt.close(fig2)
        paths["feature_importance"] = p2
    paths["prob_hist"] = p1
    return paths

def _watermark(c: Any, text: str, width: float, height: float) -> None:
    c.saveState()
    c.setFillGray(0.9, 0.3)
    c.setFont("Helvetica", 48)
    c.translate(width/2, height/2)
    c.rotate(30)
    c.drawCentredString(0, 0, text)
    c.restoreState()

def _render_pdf(path: str, summary: Dict[str, Any], sections: Dict[str, str], charts: Dict[str, str], watermark: Optional[str] = None) -> str:
    c = pdf_canvas.Canvas(path, pagesize=A4)
    width, height = A4

    # Cover
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2*cm, height-2*cm, "Anomaly Detection Report")
    c.setFont("Helvetica", 11)
    c.drawString(2*cm, height-3*cm, f"Analysis ID: {summary['analysis_id']}")
    c.drawString(2*cm, height-3.7*cm, f"Generated: {datetime.now(timezone.utc).isoformat()}")
    if watermark:
        _watermark(c, watermark, width, height)
    c.showPage()

    # Sections
    for title, body in [
        ("Executive Summary", sections.get("executive_summary", "")),
        ("Technical Details", sections.get("technical_details", "")),
        ("Recommendations", sections.get("recommendations", "")),
        ("Risk Assessment", sections.get("risk_assessment", "")),
        ("Action Items", sections.get("action_items", "")),
        ("Visualizations", sections.get("viz_descriptions", "")),
    ]:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(2*cm, height-2*cm, title)
        c.setFont("Helvetica", 10)
        text = c.beginText(2*cm, height-3*cm)
        for line in body.splitlines() or [""]:
            text.textLine(line[:120])
        c.drawText(text)
        if watermark:
            _watermark(c, watermark, width, height)
        c.showPage()

    # Charts
    for label, img_path in charts.items():
        c.setFont("Helvetica-Bold", 12)
        c.drawString(2*cm, height-2*cm, label.replace('_', ' ').title())
        try:
            img = ImageReader(img_path)
            c.drawImage(img, 2*cm, height/2-6*cm, width=16*cm, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass
        if watermark:
            _watermark(c, watermark, width, height)
        c.showPage()

    c.save()
    return path

def _render_html(path: str, sections: Dict[str, str], charts: Dict[str, str]) -> str:
    def img_to_b64(p: str) -> str:
        with open(p, "rb") as f:
            return base64.b64encode(f.read()).decode()
    imgs = {k: img_to_b64(v) for k, v in charts.items()}
    html = f"""
<html><head><meta charset='utf-8'><title>Anomaly Report</title></head>
<body>
<h1>Executive Summary</h1><p>{sections.get('executive_summary','').replace('\n','<br/>')}</p>
<h2>Technical Details</h2><pre>{sections.get('technical_details','')}</pre>
<h2>Recommendations</h2><pre>{sections.get('recommendations','')}</pre>
<h2>Risk Assessment</h2><pre>{sections.get('risk_assessment','')}</pre>
<h2>Action Items</h2><pre>{sections.get('action_items','')}</pre>
<h2>Visualizations</h2><pre>{sections.get('viz_descriptions','')}</pre>
<h2>Charts</h2>
{''.join(f"<div><h3>{k}</h3><img style='max-width:800px' src='data:image/png;base64,{v}'/></div>" for k,v in imgs.items())}
</body></html>
"""
    with open(path, "wt", encoding="utf-8") as f:
        f.write(html)
    return path

def _compress(paths: List[str], out_zip: str) -> str:
    with zipfile.ZipFile(out_zip, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in paths:
            if os.path.exists(p):
                z.write(p, arcname=os.path.basename(p))
    return out_zip

def _send_email(subject: str, body: str, attachments: List[str], recipients: List[str]) -> None:
    host = os.getenv("SMTP_HOST")
    if not host:
        logger.info("Email disabled (no SMTP_HOST)")
        return
    import smtplib
    from email.message import EmailMessage
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("SMTP_FROM", "noreply@example.com")
    msg["To"] = ", ".join(recipients)
    msg.set_content(body)
    for p in attachments:
        try:
            with open(p, "rb") as f:
                data = f.read()
            msg.add_attachment(data, maintype="application", subtype="octet-stream", filename=os.path.basename(p))
        except Exception:
            logger.debug("attach-failed", exc_info=True)
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd = os.getenv("SMTP_PASS")
    use_tls = os.getenv("SMTP_TLS", "true").lower() == "true"
    with smtplib.SMTP(host, port) as s:
        if use_tls:
            s.starttls()
        if user and pwd:
            s.login(user, pwd)
        s.send_message(msg)

@report_app.task(bind=True, name="generate_report_task", acks_late=True)
def generate_report_task(self, *, user_id: int, analysis_id: str, format: str = "pdf", recipients: Optional[List[str]] = None, watermark: Optional[str] = None) -> Dict[str, Any]:
    data = get_cached_results(analysis_id) if callable(get_cached_results) else None
    if not data:
        raise ValueError("analysis results not found")

    summary = data.get("summary", {})
    anomalies = data.get("anomalies", [])

    # Generate content via LLM
    gen = ReportGenerator()
    rep = gen.generate(analysis_summary=summary, anomalies=anomalies)
    sections = {
        "executive_summary": rep.executive_summary.content,
        "technical_details": rep.technical_details.content,
        "recommendations": rep.recommendations.content,
        "risk_assessment": rep.risk_assessment.content,
        "action_items": rep.action_items.content,
        "viz_descriptions": rep.viz_descriptions.content,
    }

    charts = _make_charts(summary, anomalies)
    base = os.path.join(REPORT_DIR, f"report_{analysis_id}")
    outputs: List[str] = []

    if format == "pdf":
        pdf_path = base + ".pdf"
        _render_pdf(pdf_path, summary, sections, charts, watermark=watermark)
        outputs.append(pdf_path)
    elif format == "html":
        html_path = base + ".html"
        _render_html(html_path, sections, charts)
        outputs.append(html_path)
    elif format == "json":
        json_path = base + ".json"
        payload = {"summary": summary, "sections": sections, "charts": list(charts.keys())}
        with open(json_path, "wt", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        outputs.append(json_path)
    else:
        raise ValueError("unsupported format")

    # Zip assets alongside main output
    zip_path = base + ".zip"
    _compress(outputs + list(charts.values()), zip_path)

    if recipients:
        _send_email("Anomaly Report", "Please find the attached report.", [zip_path], recipients)

    return {"report_files": outputs, "bundle": zip_path}