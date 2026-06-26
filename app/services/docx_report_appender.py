from __future__ import annotations

import re
from copy import deepcopy
from pathlib import Path, PurePosixPath
from tempfile import NamedTemporaryFile
from zipfile import ZIP_DEFLATED, ZipFile

from lxml import etree

from app.models.project import Project


WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
CONTENT_TYPES_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
REPORT_SECTION_TOP_MARGIN_TWIPS = "2000"
PHOTO_SECTION_TOP_MARGIN_TWIPS = "1800"

NS = {"w": WORD_NS, "r": REL_NS, "rel": PKG_REL_NS, "ct": CONTENT_TYPES_NS}

IMAGE_CONTENT_TYPES = {
    "bmp": "image/bmp",
    "gif": "image/gif",
    "jpeg": "image/jpeg",
    "jpg": "image/jpeg",
    "png": "image/png",
    "tif": "image/tiff",
    "tiff": "image/tiff",
    "wmf": "image/x-wmf",
    "emf": "image/x-emf",
}


def append_source_work_reports(docx_path: Path, project: Project) -> None:
    """Append original work-report sections from uploaded DOCX files to a generated ACTA."""
    source_paths = [
        Path(source.stored_path)
        for source in sorted(project.source_documents, key=lambda item: item.uploaded_at)
        if source.stored_path and Path(source.stored_path).exists()
    ]
    if not source_paths:
        return

    with ZipFile(docx_path, "r") as target_zip:
        files = {name: target_zip.read(name) for name in target_zip.namelist()}

    target_document = etree.fromstring(files["word/document.xml"])
    target_rels = _load_relationships(files.get("word/_rels/document.xml.rels"))
    content_types = etree.fromstring(files["[Content_Types].xml"])

    appended_any = False
    for source_path in source_paths:
        with ZipFile(source_path, "r") as source_zip:
            source_document = etree.fromstring(source_zip.read("word/document.xml"))
            report_elements = _report_body_elements(source_document)
            if not report_elements:
                continue
            _append_report_section_break(target_document, REPORT_SECTION_TOP_MARGIN_TWIPS)
            appended_any = True
            source_rels = _load_relationships(source_zip.read("word/_rels/document.xml.rels"))
            pending_photo_section = False
            for index, element in enumerate(report_elements):
                if pending_photo_section:
                    if _is_empty_spacer_paragraph(element):
                        continue
                    _append_report_section_break(target_document, PHOTO_SECTION_TOP_MARGIN_TWIPS)
                    pending_photo_section = False
                copied = deepcopy(element)
                _materialize_no_spacing_style(copied)
                _normalize_report_table(copied)
                _copy_relationships(copied, source_zip, source_rels, files, target_rels, content_types)
                _append_body_element(target_document, copied)
                if _is_signature_table(element) and _has_photo_section_before_next_report(report_elements, index + 1):
                    pending_photo_section = True

    if not appended_any:
        return

    files["word/document.xml"] = etree.tostring(
        target_document,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )
    files["word/_rels/document.xml.rels"] = etree.tostring(
        target_rels,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )
    files["[Content_Types].xml"] = etree.tostring(
        content_types,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )
    _rewrite_docx(docx_path, files)


def _report_body_elements(document: etree._Element) -> list[etree._Element]:
    body = document.find("w:body", NS)
    if body is None:
        return []
    children = [child for child in body if child.tag != f"{{{WORD_NS}}}sectPr"]
    start_index = next(
        (index for index, child in enumerate(children) if "REPORTE DE TRABAJO" in _canonical_text(child)),
        None,
    )
    if start_index is None:
        return []
    return children[start_index:]


def _append_report_section_break(target_document: etree._Element, top_margin_twips: str) -> None:
    section_break = etree.Element(f"{{{WORD_NS}}}p")
    paragraph_properties = etree.SubElement(section_break, f"{{{WORD_NS}}}pPr")
    section_properties = _section_break_properties(target_document)
    paragraph_properties.append(section_properties)
    _append_body_element(target_document, section_break)
    _set_body_section_top_margin(target_document, top_margin_twips)


def _section_break_properties(target_document: etree._Element) -> etree._Element:
    section_properties = deepcopy(_last_section_properties(target_document))
    section_type = section_properties.find("w:type", NS)
    if section_type is None:
        section_type = etree.Element(f"{{{WORD_NS}}}type")
        section_properties.insert(0, section_type)
    section_type.set(f"{{{WORD_NS}}}val", "nextPage")

    return section_properties


def _last_section_properties(document: etree._Element) -> etree._Element:
    body = document.find("w:body", NS)
    if body is None:
        return etree.Element(f"{{{WORD_NS}}}sectPr")
    section_properties = body.find("w:sectPr", NS)
    if section_properties is not None:
        return section_properties
    for section_properties in reversed(body.xpath(".//w:pPr/w:sectPr", namespaces=NS)):
        return section_properties
    return etree.Element(f"{{{WORD_NS}}}sectPr")


def _set_body_section_top_margin(document: etree._Element, top_margin_twips: str) -> None:
    body = document.find("w:body", NS)
    if body is None:
        return
    section_properties = body.find("w:sectPr", NS)
    if section_properties is None:
        section_properties = etree.SubElement(body, f"{{{WORD_NS}}}sectPr")
    page_margin = section_properties.find("w:pgMar", NS)
    if page_margin is None:
        page_margin = etree.SubElement(section_properties, f"{{{WORD_NS}}}pgMar")
    page_margin.set(f"{{{WORD_NS}}}top", top_margin_twips)


def _append_body_element(document: etree._Element, element: etree._Element) -> None:
    body = document.find("w:body", NS)
    if body is None:
        return
    sect_pr = body.find("w:sectPr", NS)
    if sect_pr is not None:
        body.insert(body.index(sect_pr), element)
    else:
        body.append(element)


def _normalize_report_table(element: etree._Element) -> None:
    if element.tag != f"{{{WORD_NS}}}tbl":
        return
    text = _canonical_text(element)
    if "ACTIVIDADES REALIZADAS" in text:
        _normalize_activities_table(element)
    elif "ENTREGA" in text and "RECIBIO" in text:
        _normalize_signature_table(element)


def _is_signature_table(element: etree._Element) -> bool:
    if element.tag != f"{{{WORD_NS}}}tbl":
        return False
    text = _canonical_text(element)
    return "ENTREGA" in text and "RECIBIO" in text


def _has_photo_section_before_next_report(elements: list[etree._Element], start_index: int) -> bool:
    for element in elements[start_index:]:
        text = _canonical_text(element)
        if "REPORTE DE TRABAJO" in text:
            return False
        if "REPORTE FOTOGRAFICO" in text:
            return True
    return False


def _is_empty_spacer_paragraph(element: etree._Element) -> bool:
    if element.tag != f"{{{WORD_NS}}}p" or _canonical_text(element):
        return False
    return not element.xpath(".//w:br | .//w:drawing | .//w:pict | .//w:object", namespaces=NS)


def _normalize_activities_table(element: etree._Element) -> None:
    table_properties = _table_properties(element)
    _remove_child(table_properties, "tblStyle")
    _set_table_borders(table_properties)
    _set_compact_table_paragraphs(element)


def _normalize_signature_table(element: etree._Element) -> None:
    table_properties = _table_properties(element)
    _remove_child(table_properties, "tblStyle")
    _remove_child(table_properties, "tblpPr")

    grid_widths = [
        int(column.get(f"{{{WORD_NS}}}w"))
        for column in element.xpath("./w:tblGrid/w:gridCol", namespaces=NS)
        if (column.get(f"{{{WORD_NS}}}w") or "").isdigit()
    ]
    if grid_widths:
        table_width = table_properties.find("w:tblW", NS)
        if table_width is None:
            table_width = etree.SubElement(table_properties, f"{{{WORD_NS}}}tblW")
        table_width.set(f"{{{WORD_NS}}}w", str(sum(grid_widths)))
        table_width.set(f"{{{WORD_NS}}}type", "dxa")

    for row in element.xpath("./w:tr", namespaces=NS):
        row_properties = row.find("w:trPr", NS)
        if row_properties is None:
            row_properties = etree.Element(f"{{{WORD_NS}}}trPr")
            row.insert(0, row_properties)
        if row_properties.find("w:cantSplit", NS) is None:
            etree.SubElement(row_properties, f"{{{WORD_NS}}}cantSplit")

    _set_compact_table_paragraphs(element)


def _table_properties(element: etree._Element) -> etree._Element:
    table_properties = element.find("w:tblPr", NS)
    if table_properties is None:
        table_properties = etree.Element(f"{{{WORD_NS}}}tblPr")
        element.insert(0, table_properties)
    return table_properties


def _set_compact_table_paragraphs(element: etree._Element) -> None:
    for paragraph in element.xpath(".//w:p", namespaces=NS):
        paragraph_properties = paragraph.find("w:pPr", NS)
        if paragraph_properties is None:
            paragraph_properties = etree.Element(f"{{{WORD_NS}}}pPr")
            paragraph.insert(0, paragraph_properties)

        _remove_child(paragraph_properties, "pStyle")

        spacing = paragraph_properties.find("w:spacing", NS)
        if spacing is None:
            spacing = etree.SubElement(paragraph_properties, f"{{{WORD_NS}}}spacing")
        spacing.set(f"{{{WORD_NS}}}before", "0")
        spacing.set(f"{{{WORD_NS}}}after", "0")
        spacing.set(f"{{{WORD_NS}}}line", "240")
        spacing.set(f"{{{WORD_NS}}}lineRule", "auto")


def _materialize_no_spacing_style(element: etree._Element) -> None:
    for paragraph_properties in element.xpath(
        './/w:pPr[w:pStyle[@w:val="Sinespaciado"]]',
        namespaces=NS,
    ):
        _remove_child(paragraph_properties, "pStyle")
        spacing = paragraph_properties.find("w:spacing", NS)
        if spacing is None:
            spacing = etree.SubElement(paragraph_properties, f"{{{WORD_NS}}}spacing")
        spacing.set(f"{{{WORD_NS}}}before", "0")
        spacing.set(f"{{{WORD_NS}}}after", "0")
        spacing.set(f"{{{WORD_NS}}}line", "240")
        spacing.set(f"{{{WORD_NS}}}lineRule", "auto")


def _set_table_borders(table_properties: etree._Element) -> None:
    borders = table_properties.find("w:tblBorders", NS)
    if borders is None:
        borders = etree.SubElement(table_properties, f"{{{WORD_NS}}}tblBorders")
    for border_name in ("top", "left", "bottom", "right", "insideH", "insideV"):
        border = borders.find(f"w:{border_name}", NS)
        if border is None:
            border = etree.SubElement(borders, f"{{{WORD_NS}}}{border_name}")
        border.set(f"{{{WORD_NS}}}val", "single")
        border.set(f"{{{WORD_NS}}}sz", "4")
        border.set(f"{{{WORD_NS}}}space", "0")
        border.set(f"{{{WORD_NS}}}color", "000000")


def _remove_child(parent: etree._Element, child_name: str) -> None:
    child = parent.find(f"w:{child_name}", NS)
    if child is not None:
        parent.remove(child)


def _load_relationships(raw_xml: bytes | None) -> etree._Element:
    if raw_xml:
        return etree.fromstring(raw_xml)
    return etree.Element(f"{{{PKG_REL_NS}}}Relationships")


def _copy_relationships(
    element: etree._Element,
    source_zip: ZipFile,
    source_rels: etree._Element,
    target_files: dict[str, bytes],
    target_rels: etree._Element,
    content_types: etree._Element,
) -> None:
    rels_by_id = {rel.get("Id"): rel for rel in source_rels.findall("rel:Relationship", NS)}
    for attr_name in ("id", "embed", "link"):
        rel_attr = f"{{{REL_NS}}}{attr_name}"
        for node in element.xpath(f".//*[@r:{attr_name}]", namespaces=NS):
            old_id = node.get(rel_attr)
            if not old_id or old_id not in rels_by_id:
                continue
            new_id = _copy_relationship(rels_by_id[old_id], source_zip, target_files, target_rels, content_types)
            node.set(rel_attr, new_id)


def _copy_relationship(
    source_rel: etree._Element,
    source_zip: ZipFile,
    target_files: dict[str, bytes],
    target_rels: etree._Element,
    content_types: etree._Element,
) -> str:
    new_id = _next_relationship_id(target_rels)
    rel_type = source_rel.get("Type") or ""
    target = source_rel.get("Target") or ""
    target_mode = source_rel.get("TargetMode")

    if target_mode == "External":
        _add_relationship(target_rels, new_id, rel_type, target, target_mode)
        return new_id

    source_part = _word_part_path(target)
    if source_part in source_zip.namelist():
        extension = PurePosixPath(source_part).suffix.lstrip(".").lower()
        new_target = _next_internal_target(target_files, extension)
        target_files[f"word/{new_target}"] = source_zip.read(source_part)
        _ensure_default_content_type(content_types, extension)
        target = new_target

    _add_relationship(target_rels, new_id, rel_type, target, target_mode)
    return new_id


def _word_part_path(target: str) -> str:
    path = PurePosixPath("word") / target
    normalized: list[str] = []
    for part in path.parts:
        if part == "..":
            if normalized:
                normalized.pop()
        elif part != ".":
            normalized.append(part)
    return str(PurePosixPath(*normalized))


def _next_internal_target(target_files: dict[str, bytes], extension: str) -> str:
    extension = extension or "bin"
    index = 1
    while True:
        candidate = f"media/appended_report_{index}.{extension}"
        if f"word/{candidate}" not in target_files:
            return candidate
        index += 1


def _ensure_default_content_type(content_types: etree._Element, extension: str) -> None:
    if not extension:
        return
    if content_types.xpath(f'ct:Default[@Extension="{extension}"]', namespaces=NS):
        return
    content_type = IMAGE_CONTENT_TYPES.get(extension, "application/octet-stream")
    default = etree.Element(f"{{{CONTENT_TYPES_NS}}}Default")
    default.set("Extension", extension)
    default.set("ContentType", content_type)
    content_types.insert(0, default)


def _add_relationship(
    target_rels: etree._Element,
    rel_id: str,
    rel_type: str,
    target: str,
    target_mode: str | None,
) -> None:
    rel = etree.Element(f"{{{PKG_REL_NS}}}Relationship")
    rel.set("Id", rel_id)
    rel.set("Type", rel_type)
    rel.set("Target", target)
    if target_mode:
        rel.set("TargetMode", target_mode)
    target_rels.append(rel)


def _next_relationship_id(target_rels: etree._Element) -> str:
    used = {
        int(match.group(1))
        for rel in target_rels.findall("rel:Relationship", NS)
        if (match := re.fullmatch(r"rId(\d+)", rel.get("Id") or ""))
    }
    next_id = max(used, default=0) + 1
    while next_id in used:
        next_id += 1
    return f"rId{next_id}"


def _canonical_text(element: etree._Element) -> str:
    text = " ".join("".join(element.xpath(".//w:t/text()", namespaces=NS)).split())
    return (
        text.upper()
        .replace("Á", "A")
        .replace("É", "E")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Ú", "U")
        .replace("Ü", "U")
    )


def _rewrite_docx(path: Path, files: dict[str, bytes]) -> None:
    with NamedTemporaryFile(delete=False, suffix=".docx") as temp_file:
        temp_path = Path(temp_file.name)
    try:
        with ZipFile(temp_path, "w", compression=ZIP_DEFLATED) as output_zip:
            for name, content in files.items():
                output_zip.writestr(name, content)
        temp_path.replace(path)
    finally:
        temp_path.unlink(missing_ok=True)
