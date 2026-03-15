"""Export service for generating report files in various formats."""

import io
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.logging import get_logger
from app.models.report import ReportFormat

logger = get_logger(__name__)


class ExportService:
    """Service for exporting report data to various file formats."""

    def __init__(self, output_dir: str | None = None):
        """Initialize export service.

        Args:
            output_dir: Directory for output files (defaults to settings.REPORTS_DIR)
        """
        self.output_dir = Path(output_dir or getattr(settings, 'REPORTS_DIR', '/tmp/reports'))
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export(
        self,
        report_id: uuid.UUID,
        data: dict[str, Any],
        format: ReportFormat,
        title: str,
    ) -> str:
        """Export report data to file.

        Args:
            report_id: Report ID for filename
            data: Report data dictionary
            format: Output format
            title: Report title for filename

        Returns:
            Path to generated file
        """
        exporters = {
            ReportFormat.JSON: self._export_json,
            ReportFormat.CSV: self._export_csv,
            ReportFormat.EXCEL: self._export_excel,
            ReportFormat.PDF: self._export_pdf,
        }

        exporter = exporters.get(format)
        if not exporter:
            raise ValueError(f"Unsupported export format: {format}")

        return exporter(report_id, data, title)

    def _export_json(
        self,
        report_id: uuid.UUID,
        data: dict[str, Any],
        title: str,
    ) -> str:
        """Export to JSON format."""
        filename = f"{report_id}_{self._sanitize_filename(title)}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        logger.info(f"Exported JSON report to {filepath}")
        return str(filepath)

    def _export_csv(
        self,
        report_id: uuid.UUID,
        data: dict[str, Any],
        title: str,
    ) -> str:
        """Export to CSV format."""
        import csv

        filename = f"{report_id}_{self._sanitize_filename(title)}.csv"
        filepath = self.output_dir / filename

        # Find the main data list to export
        items = self._find_exportable_items(data)

        if not items:
            # If no list found, create summary CSV
            items = [self._flatten_dict(data)]

        # Get all unique keys across items
        all_keys = set()
        for item in items:
            if isinstance(item, dict):
                all_keys.update(item.keys())
        headers = sorted(all_keys)

        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
            writer.writeheader()
            for item in items:
                if isinstance(item, dict):
                    # Flatten nested dicts
                    flat_item = self._flatten_dict(item)
                    writer.writerow(flat_item)

        logger.info(f"Exported CSV report to {filepath}")
        return str(filepath)

    def _export_excel(
        self,
        report_id: uuid.UUID,
        data: dict[str, Any],
        title: str,
    ) -> str:
        """Export to Excel format."""
        import pandas as pd

        filename = f"{report_id}_{self._sanitize_filename(title)}.xlsx"
        filepath = self.output_dir / filename

        with pd.ExcelWriter(filepath, engine="openpyxl") as writer:
            # Summary sheet
            if "summary" in data:
                summary_df = pd.DataFrame([self._flatten_dict(data["summary"])])
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

            # Find data lists and create sheets for each
            for key, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    sheet_name = key[:31]  # Excel sheet name limit
                    df = pd.DataFrame([self._flatten_dict(item) for item in value])
                    df.to_excel(writer, sheet_name=sheet_name, index=False)

            # If no sheets created, export entire data as single sheet
            if not writer.sheets:
                df = pd.DataFrame([self._flatten_dict(data)])
                df.to_excel(writer, sheet_name="Report", index=False)

        logger.info(f"Exported Excel report to {filepath}")
        return str(filepath)

    def _export_pdf(
        self,
        report_id: uuid.UUID,
        data: dict[str, Any],
        title: str,
    ) -> str:
        """Export to PDF format using simple HTML to PDF conversion."""
        try:
            from weasyprint import HTML, CSS
            has_weasyprint = True
        except ImportError:
            has_weasyprint = False
            logger.warning("weasyprint not available, falling back to text-based PDF")

        filename = f"{report_id}_{self._sanitize_filename(title)}.pdf"
        filepath = self.output_dir / filename

        # Generate HTML content
        html_content = self._generate_html_report(data, title)

        if has_weasyprint:
            # Use weasyprint for proper PDF generation
            html = HTML(string=html_content)
            css = CSS(string="""
                body { font-family: Arial, sans-serif; font-size: 12px; margin: 20px; }
                h1 { color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }
                h2 { color: #555; margin-top: 20px; }
                table { border-collapse: collapse; width: 100%; margin: 10px 0; }
                th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
                th { background-color: #f4f4f4; font-weight: bold; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .summary { background-color: #e8f4f8; padding: 15px; margin: 10px 0; border-radius: 5px; }
                .metric { display: inline-block; margin: 10px 20px 10px 0; }
                .metric-value { font-size: 24px; font-weight: bold; color: #2563eb; }
                .metric-label { font-size: 12px; color: #666; }
            """)
            html.write_pdf(filepath, stylesheets=[css])
        else:
            # Fallback: Save as HTML with .pdf extension (not ideal but works)
            # In production, you'd want to ensure weasyprint or reportlab is installed
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet

            doc = SimpleDocTemplate(str(filepath), pagesize=letter)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            elements.append(Paragraph(title, styles['Heading1']))
            elements.append(Spacer(1, 12))

            # Generated timestamp
            elements.append(Paragraph(
                f"Generated: {data.get('generated_at', datetime.now().isoformat())}",
                styles['Normal']
            ))
            elements.append(Spacer(1, 24))

            # Summary section
            if "summary" in data:
                elements.append(Paragraph("Summary", styles['Heading2']))
                summary = data["summary"]
                summary_data = [[k, str(v)] for k, v in summary.items()]
                if summary_data:
                    t = Table(summary_data, colWidths=[200, 200])
                    t.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, -1), colors.whitesmoke),
                        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 0), (-1, -1), 10),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
                    ]))
                    elements.append(t)
                elements.append(Spacer(1, 12))

            doc.build(elements)

        logger.info(f"Exported PDF report to {filepath}")
        return str(filepath)

    def _generate_html_report(self, data: dict[str, Any], title: str) -> str:
        """Generate HTML content for PDF export."""
        html_parts = [
            "<!DOCTYPE html>",
            "<html><head><meta charset='utf-8'></head><body>",
            f"<h1>{title}</h1>",
            f"<p>Generated: {data.get('generated_at', datetime.now().isoformat())}</p>",
        ]

        # Summary section
        if "summary" in data:
            html_parts.append("<div class='summary'><h2>Summary</h2>")
            for key, value in data["summary"].items():
                label = key.replace("_", " ").title()
                html_parts.append(
                    f"<div class='metric'>"
                    f"<div class='metric-value'>{value}</div>"
                    f"<div class='metric-label'>{label}</div></div>"
                )
            html_parts.append("</div>")

        # Data tables
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                html_parts.append(f"<h2>{key.replace('_', ' ').title()}</h2>")
                html_parts.append("<table>")

                # Headers
                headers = list(value[0].keys())
                html_parts.append("<tr>" + "".join(f"<th>{h}</th>" for h in headers) + "</tr>")

                # Rows (limit to 100 for PDF)
                for item in value[:100]:
                    cells = [str(item.get(h, "")) for h in headers]
                    html_parts.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")

                html_parts.append("</table>")

        html_parts.append("</body></html>")
        return "\n".join(html_parts)

    def _find_exportable_items(self, data: dict[str, Any]) -> list[dict]:
        """Find the main list of items to export from report data."""
        # Look for common list keys
        list_keys = ["items", "runs", "jobs", "exceptions", "anomalies", "records"]

        for key in list_keys:
            if key in data and isinstance(data[key], list):
                return data[key]

        # Look for any list in the data
        for key, value in data.items():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value

        return []

    def _flatten_dict(self, d: dict[str, Any], parent_key: str = "", sep: str = "_") -> dict[str, Any]:
        """Flatten nested dictionary."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep).items())
            elif isinstance(v, list):
                # Convert list to string representation
                items.append((new_key, str(v)))
            else:
                items.append((new_key, v))
        return dict(items)

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for filesystem."""
        # Remove or replace invalid characters
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, "_")
        # Limit length and strip
        return filename[:50].strip()


def get_export_service() -> ExportService:
    """Factory function to create export service."""
    return ExportService()
