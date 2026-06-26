from __future__ import annotations

import re

from tests.conftest import DOCX_MIME, make_docx_bytes


def _create_project(client) -> str:
    response = client.post(
        "/projects",
        data={"name": "Proyecto de prueba", "center_name": "Unidad Medica"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    location = response.headers["location"]
    match = re.search(r"/projects/([^/]+)$", location)
    assert match is not None
    return match.group(1)


def test_project_crud_pages(isolated_client) -> None:
    client = isolated_client
    response = client.get("/projects")
    assert response.status_code == 200
    assert "Proyectos" in response.text

    project_id = _create_project(client)
    detail = client.get(f"/projects/{project_id}")
    assert detail.status_code == 200
    assert "Proyecto de prueba" in detail.text
    assert "Unidad Medica" in detail.text


def test_upload_two_docx_files_for_project(isolated_client) -> None:
    client = isolated_client
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents",
        files=[
            ("files", ("minisplit.docx", make_docx_bytes("TIPO DE UNIDAD: MINISPLIT"), DOCX_MIME)),
            ("files", ("paquete.docx", make_docx_bytes("TIPO DE UNIDAD: TIPO PAQUETE"), DOCX_MIME)),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303

    detail = client.get(f"/projects/{project_id}")
    assert "minisplit.docx" in detail.text
    assert "paquete.docx" in detail.text
    assert "UPLOADED" in detail.text


def test_upload_rejects_invalid_docx_and_keeps_project(isolated_client) -> None:
    client = isolated_client
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents",
        files=[("files", ("broken.docx", b"not a real document", DOCX_MIME))],
    )
    assert response.status_code == 400
    assert "estructura ZIP valida" in response.text
    assert "broken.docx" in response.text


def test_upload_rejects_duplicate_file_in_same_batch(isolated_client) -> None:
    client = isolated_client
    project_id = _create_project(client)
    payload = make_docx_bytes("documento duplicado")
    response = client.post(
        f"/projects/{project_id}/documents",
        files=[
            ("files", ("one.docx", payload, DOCX_MIME)),
            ("files", ("two.docx", payload, DOCX_MIME)),
        ],
    )
    assert response.status_code == 400
    assert "ya fue cargado" in response.text


def test_analyze_mixed_project_from_two_uploaded_docx_files(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    analyze = client.get(f"/projects/{project_id}/analysis")
    assert analyze.status_code == 200
    assert "MINISPLIT: 1" in analyze.text
    assert "PACKAGE: 1" in analyze.text
    assert "MS123" in analyze.text
    assert "PK999" in analyze.text


def test_review_general_updates_project_lots_and_signatures(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    response = client.post(
        f"/projects/{project_id}/review/general",
        data={
            "name": "Proyecto revisado",
            "center_name": "Hospital Revisado",
            "location": "Tapachula",
            "state": "Chiapas",
            "service_date_raw": "10 DE JUNIO DE 2026",
            "contract_date_raw": "01 DE JUNIO DE 2026",
            "order_number": "ABC-999",
            "client_name": "Cliente revisado",
            "lots_text": "01\n02\n03",
            "deliverer_name": "Persona Entrega",
            "deliverer_position": "Supervisor",
            "receiver_name": "Persona Recibe",
            "receiver_position": "Responsable",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Hospital Revisado" in response.text
    assert "ABC-999" in response.text
    assert "Persona Recibe" in response.text
    assert ">03<" in response.text or "03" in response.text


def test_single_manual_lot_is_assigned_to_unassigned_equipment(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    response = client.post(
        f"/projects/{project_id}/review/general",
        data={
            "name": "Proyecto lote",
            "center_name": "Hospital",
            "location": "Tapachula",
            "state": "Chiapas",
            "service_date_raw": "10 DE JUNIO DE 2026",
            "contract_date_raw": "01 DE JUNIO DE 2026",
            "order_number": "ABC-123",
            "client_name": "Cliente",
            "lots_text": "3",
            "deliverer_name": "",
            "deliverer_position": "",
            "receiver_name": "",
            "receiver_position": "",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    equipment_page = client.get(f"/projects/{project_id}/review/equipment")
    assert equipment_page.text.count("selected>3</option>") >= 2


def test_review_equipment_add_update_delete_and_merge(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    added = client.post(
        f"/projects/{project_id}/equipment",
        data={
            "equipment_type": "MINISPLIT",
            "zone": "AREA NUEVA",
            "brand": "LG",
            "capacity": "2 TON",
            "serial": "NEW123",
            "notes": "Alta manual",
        },
        follow_redirects=True,
    )
    assert added.status_code == 200
    assert "NEW123" in added.text

    update_match = re.search(r"/equipment/([^/]+)/update", added.text)
    assert update_match is not None
    equipment_id = update_match.group(1)
    updated = client.post(
        f"/projects/{project_id}/equipment/{equipment_id}/update",
        data={
            "equipment_type": "PACKAGE",
            "zone": "AREA EDITADA",
            "brand": "TRANE",
            "capacity": "5 TON",
            "serial": "EDIT123",
            "notes": "Editado manualmente",
        },
        follow_redirects=True,
    )
    assert "AREA EDITADA" in updated.text
    assert "EDIT123" in updated.text

    ids = re.findall(r"/equipment/([^/]+)/update", updated.text)
    assert len(ids) >= 2
    merged = client.post(
        f"/projects/{project_id}/equipment/{ids[-1]}/merge",
        data={"target_equipment_id": ids[0]},
        follow_redirects=True,
    )
    assert merged.status_code == 200


def test_review_work_add_update_and_delete(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    work_page = client.get(f"/projects/{project_id}/review/work")
    assert work_page.status_code == 200
    equipment_match = re.search(r"/equipment/([^/]+)/work", work_page.text)
    assert equipment_match is not None
    equipment_id = equipment_match.group(1)

    created = client.post(
        f"/projects/{project_id}/equipment/{equipment_id}/work",
        data={"title": "CAPACITOR", "description": "SUSTITUIDO EN REVISION."},
        follow_redirects=True,
    )
    assert "CAPACITOR" in created.text
    work_match = re.search(r"/work/([^/]+)/update", created.text)
    assert work_match is not None
    work_item_id = work_match.group(1)

    updated = client.post(
        f"/projects/{project_id}/work/{work_item_id}/update",
        data={"title": "CAPACITOR EDITADO", "description": "Descripcion revisada."},
        follow_redirects=True,
    )
    assert "CAPACITOR EDITADO" in updated.text
    deleted = client.post(f"/projects/{project_id}/work/{work_item_id}/delete", follow_redirects=True)
    assert deleted.status_code == 200


def test_generate_excel_and_download_artifact(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    response = client.post(
        f"/projects/{project_id}/review/general",
        data={
            "name": "Proyecto Excel",
            "center_name": "Hospital Excel",
            "location": "Tapachula",
            "state": "Chiapas",
            "service_date_raw": "10 DE JUNIO DE 2026",
            "contract_date_raw": "01 DE JUNIO DE 2026",
            "order_number": "ABC-123",
            "client_name": "Cliente",
            "lots_text": "01\n02",
            "deliverer_name": "Entrega",
            "deliverer_position": "Cargo Entrega",
            "receiver_name": "Recibe",
            "receiver_position": "Cargo Recibe",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200

    generated = client.post(f"/projects/{project_id}/generate", data={"action": "excel"}, follow_redirects=True)
    assert generated.status_code == 200
    assert "EXCEL_XLSX" in generated.text
    download_match = re.search(rf"/projects/{project_id}/artifacts/([^\"']+)", generated.text)
    assert download_match is not None
    download = client.get(f"/projects/{project_id}/artifacts/{download_match.group(1)}")
    assert download.status_code == 200
    assert download.content.startswith(b"PK")


def test_generate_acta_annex_zip_and_download_artifacts(isolated_client) -> None:
    client = isolated_client
    project_id = _create_analyzed_mixed_project(client)
    for action, artifact_type in [("acta", "ACTA_DOCX"), ("annex", "ANNEX_DOCX"), ("zip", "PROJECT_ZIP")]:
        response = client.post(f"/projects/{project_id}/generate", data={"action": action}, follow_redirects=True)
        assert response.status_code == 200
        assert artifact_type in response.text
    downloads = re.findall(rf"/projects/{project_id}/artifacts/([^\"']+)", response.text)
    assert downloads
    downloaded = client.get(f"/projects/{project_id}/artifacts/{downloads[-1]}")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"PK")


def _create_analyzed_mixed_project(client) -> str:
    project_id = _create_project(client)
    response = client.post(
        f"/projects/{project_id}/documents",
        files=[
            (
                "files",
                (
                    "minisplit.docx",
                    make_docx_bytes(
                        "TAPACHULA, CHIAPAS A 10 DE JUNIO DE 2026\n"
                        "REPORTE DE TRABAJO\n"
                        "NOMBRE DEL CLIENTE: HOSPITAL GENERAL\n"
                        "PEDIDO: ABC-123\n"
                        "LOTE: 01\n"
                        "TIPO DE UNIDAD: MINISPLIT\n"
                        "ZONA: CONSULTORIO 1\n"
                        "MARCA: YORK\n"
                        "CAPACIDAD: 1 TON\n"
                        "SERIE: MS123\n"
                        "ACTIVIDADES REALIZADAS\n"
                        "Cambio de capacitor."
                    ),
                    DOCX_MIME,
                ),
            ),
            (
                "files",
                (
                    "paquete.docx",
                    make_docx_bytes(
                        "REPORTE DE TRABAJO\n"
                        "LOTE: 02\n"
                        "TIPO DE UNIDAD: TIPO PAQUETE\n"
                        "ZONA DE EQUIPO 02\n"
                        "MARCA: TRANE\n"
                        "CAPACIDAD: 20 TON.\n"
                        "SERIE: PK999\n"
                        "PIEZAS SUSTITUIDAS Y CORRECCIONES REALIZADAS\n"
                        "BANDA DE TRANSMISION: SUSTITUIDA POR DESGASTE."
                    ),
                    DOCX_MIME,
                ),
            ),
        ],
        follow_redirects=False,
    )
    assert response.status_code == 303

    analyze = client.post(f"/projects/{project_id}/analyze", follow_redirects=True)
    assert analyze.status_code == 200
    return project_id
