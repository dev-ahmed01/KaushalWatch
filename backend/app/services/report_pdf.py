from __future__ import annotations

from textwrap import wrap
from typing import Any


def _display_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"compliant", "nominal", "clear", "verified", "resolved"}:
        return "VERIFIED"
    if normalized in {"attention", "high_priority", "review", "open", "under_review", "confirmed"}:
        return "NEEDS REVIEW"
    if normalized in {"blocked", "uncertain"}:
        return "UNCERTAIN"
    if normalized in {"virtual_verification"}:
        return "OFFICER REVIEW"
    return "ANALYSIS UNAVAILABLE"


def _camera_untrusted(centre: dict[str, Any]) -> bool:
    return str(centre.get("camera_status") or "").strip().lower() in {
        "attention",
        "blocked",
        "uncertain",
    }


def _overall_status(centre: dict[str, Any]) -> str:
    if _camera_untrusted(centre):
        return "UNCERTAIN"
    return _display_status(centre.get("status"))


def _pillar_status(centre: dict[str, Any], key: str) -> str:
    if key in {"attendance_status", "practical_status", "infrastructure_status"} and _camera_untrusted(centre):
        return "UNCERTAIN"
    return _display_status(centre.get(key))


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _line(text: str, *, size: int = 10, x: int = 54, y: int = 0) -> str:
    return f"BT /F1 {size} Tf {x} {y} Td ({_pdf_escape(text)}) Tj ET"


def build_report_pdf(report: dict[str, Any]) -> bytes:
    """Build a small dependency-free PDF for the auditable centre report.

    The PDF deliberately uses built-in Helvetica and plain text so generation
    remains deterministic in offline / low-bandwidth deployments.
    """
    centre = report.get("centre") or {}
    summary = report.get("summary") or {}
    analyses = report.get("analyses") or []
    cases = report.get("cases") or []
    limitations = report.get("limitations") or []

    lines: list[tuple[str, int]] = [
        ("KAUSHALWATCH", 10),
        ("Centre Verification Report", 18),
        (f"Centre: {centre.get('name', centre.get('centre_id', 'Unknown'))}", 11),
        (f"Centre ID: {centre.get('centre_id', 'Unknown')}", 9),
        (f"Batch: {centre.get('batch_id', 'Unknown')}", 9),
        (f"Period: {report.get('period_label') or report.get('period', '7d')}", 9),
        *(([("Data: SIMULATED PROTOTYPE RECORDS", 9)] if report.get("simulated") else [])),
        ("", 9),
        ("Executive summary", 13),
        (f"Analysis runs: {summary.get('analysis_runs', 0)}", 9),
        (f"Pending cases: {summary.get('pending_cases', 0)}", 9),
        (f"Overall verification: {_overall_status(centre)}", 9),
        (f"Escalation: {(summary.get('escalation') or {}).get('label', 'Normal')}", 9),
        ("", 9),
        ("Verification pillars", 13),
        (f"Attendance: {_pillar_status(centre, 'attendance_status')}", 9),
        (f"Practical work: {_pillar_status(centre, 'practical_status')}", 9),
        (f"Infrastructure: {_pillar_status(centre, 'infrastructure_status')}", 9),
        (f"Camera integrity: {_pillar_status(centre, 'camera_status')}", 9),
        (f"Evidence integrity: {_pillar_status(centre, 'evidence_integrity_status')}", 9),
        ("", 9),
        ("Recent analyses", 13),
    ]

    for row in analyses[:14]:
        created = str(row.get("created_at") or "")
        analysis_type = str(row.get("analysis_type") or "analysis").replace("_", " ")
        outcome = str(row.get("outcome") or "unknown")
        summary_text = str(row.get("summary") or "")
        lines.append((f"{created[:19]} | {analysis_type} | {outcome}", 9))
        for segment in wrap(summary_text, width=92) or [""]:
            lines.append((f"  {segment}", 8))

    lines.extend([
        ("", 9),
        ("Cases", 13),
    ])
    if cases:
        for case in cases[:12]:
            lines.append((
                f"{case.get('case_id', 'case')} | {str(case.get('case_type', '')).replace('_', ' ')} | "
                f"{case.get('status', '')} | {case.get('severity', '')}",
                8,
            ))
            for evidence in (case.get("evidence") or [])[:4]:
                digest = str(evidence.get("sha256") or "")
                duplicate = evidence.get("duplicate_of")
                suffix = f" | duplicate of {duplicate}" if duplicate else ""
                lines.append((
                    f"  Evidence {evidence.get('evidence_id', '')} | sha256 {digest[:20]}...{suffix}",
                    7,
                ))
            edge_integrity = (case.get("details") or {}).get("edge_evidence_integrity") or []
            for evidence in edge_integrity[:4]:
                digest = str(evidence.get("sha256") or "")
                duplicate = evidence.get("duplicate_of")
                suffix = f" | duplicate of {duplicate}" if duplicate else ""
                lines.append((
                    f"  Edge evidence {evidence.get('evidence_id', '')} | sha256 {digest[:20]}...{suffix}",
                    7,
                ))
            for review in (case.get("review_history") or [])[-3:]:
                lines.append((
                    f"  Review {review.get('timestamp', '')[:19]} | "
                    f"{review.get('from_status', '')} -> {review.get('to_status', '')} | "
                    f"{review.get('actor', 'officer')}",
                    7,
                ))
                if review.get("note"):
                    for segment in wrap(str(review["note"]), width=86):
                        lines.append((f"    {segment}", 7))
    else:
        lines.append(("No compliance cases recorded in this report.", 8))

    lines.extend([
        ("", 9),
        ("Privacy and limitations", 13),
    ])
    for segment in wrap(str(report.get("privacy_note") or ""), width=96):
        lines.append((segment, 8))
    for limitation in limitations:
        for index, segment in enumerate(wrap(str(limitation), width=92)):
            lines.append(((("- " if index == 0 else "  ") + segment), 8))

    # Split into pages by approximate line budget.
    pages: list[list[tuple[str, int]]] = []
    page: list[tuple[str, int]] = []
    budget = 0
    for item in lines:
        cost = 2 if item[1] >= 13 else 1
        if budget + cost > 47 and page:
            pages.append(page)
            page = []
            budget = 0
        page.append(item)
        budget += cost
    if page:
        pages.append(page)

    objects: list[bytes] = []
    page_object_ids: list[int] = []
    content_object_ids: list[int] = []

    # 1 catalog, 2 pages tree, 3 font
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(b"")  # filled after page object IDs are known
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    next_id = 4
    for _ in pages:
        page_object_ids.append(next_id)
        content_object_ids.append(next_id + 1)
        next_id += 2

    for idx, page_lines in enumerate(pages):
        y = 790
        stream_lines: list[str] = []
        for text, size in page_lines:
            if not text:
                y -= 8
                continue
            stream_lines.append(_line(text, size=size, y=y))
            y -= 22 if size >= 13 else 15
        stream = "\n".join(stream_lines).encode("latin-1", "replace")
        page_obj = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_object_ids[idx]} 0 R >>"
        ).encode()
        content_obj = (
            f"<< /Length {len(stream)} >>\nstream\n".encode()
            + stream
            + b"\nendstream"
        )
        objects.append(page_obj)
        objects.append(content_obj)

    kids = " ".join(f"{obj_id} 0 R" for obj_id in page_object_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_object_ids)} >>".encode()

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for obj_id, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{obj_id} 0 obj\n".encode())
        output.extend(body)
        output.extend(b"\nendobj\n")

    xref = len(output)
    output.extend(f"xref\n0 {len(objects)+1}\n".encode())
    output.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        (
            f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode()
    )
    return bytes(output)
