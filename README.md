# Montebello DOCX

Aplicacion interna para cargar documentos `.docx`, revisarlos y preparar la automatizacion de ACTA, ANEXO y Excel. La fase actual cubre la base: proyectos, SQLite, almacenamiento seguro de cargas y UI inicial.

## Estado

Fases 1, 2, 3, 4, 5 y 6 implementadas:

- FastAPI con Jinja2.
- Configuracion por variables de entorno.
- SQLite con SQLAlchemy y Alembic.
- CRUD basico de proyectos.
- Carga multiple de `.docx` por proyecto.
- Validacion de extension, MIME, estructura ZIP/DOCX, limite de tamano y duplicados.
- Almacenamiento bajo `storage/uploads/{project_uuid}/{document_uuid}.docx`.
- Opcion de HTTP Basic Auth por entorno.
- Lector DOCX en orden de documento para parrafos, tablas, encabezados y pies.
- Clasificacion deterministica de documentos ACTA, WORK_REPORT, ANNEX, MIXED y UNKNOWN.
- Extraccion inicial de datos generales, lotes, equipos minisplit, equipos paquete y trabajos.
- Persistencia de resultados de analisis en SQLite con avisos de revision.
- Pantallas editables de revision para datos generales, lotes, firmas, equipos y trabajos.
- Acciones para agregar, editar, eliminar y fusionar equipos posibles duplicados.
- Resolucion manual de avisos de extraccion.
- Exportacion Excel con hojas normalizadas y hojas heredadas compatibles.
- Descarga de artefactos generados desde la UI.
- Generacion ACTA desde `[[SERVICE_SUMMARY]]` y `[[EQUIPMENT_SECTIONS]]`.
- Generacion ANEXO desde `[[ANNEX_SECTIONS]]`.
- ZIP de artefactos generados.
- Normalizacion de paquetes con `ZONA DE EQUIPO 01` y capacidades como `20 TON` o `1 TON`.
- Consolidacion de filas duplicadas paquete encabezado/detalle.
- Avisos de conflicto cuando el conteo declarado no coincide con equipos extraidos.
- Ciclo de vida FastAPI con `lifespan`, timestamps UTC, pruebas sin cache de pytest y limpieza de archivos del proyecto.
- Lote manual: el usuario captura el lote en revision y, si hay uno solo, se asigna a los equipos sin lote.
- Catalogos editables de trabajos correctivos para minisplit y paquete.
- Pruebas automatizadas de almacenamiento, flujo web y parsers.

## Archivos soportados

Solo `.docx` de Microsoft Word sin macros. No se aceptan `.docm`, `.doc`, PDF, imagenes ni OCR en el MVP.

## Configuracion

Copia `.env.example` a `.env` y ajusta los valores necesarios.

Por defecto la app se enlaza a `127.0.0.1`. Si usas `0.0.0.0` o expones la app en red local, activa `AUTH_ENABLED=true` y define `AUTH_USERNAME` y `AUTH_PASSWORD`.

## Ejecutar localmente

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Abre `http://127.0.0.1:8000`.

## Docker

```bash
docker compose up --build
```

El contenedor monta `./storage:/app/storage`. No incluyas `.env`, la base SQLite ni documentos cargados en la imagen.

## Migraciones

```bash
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
```

## Flujo previsto

1. Crear proyecto.
2. Cargar uno o mas `.docx`.
3. Analizar documentos.
4. Revisar datos generales, lotes, equipos y trabajos.
5. Exportar Excel.
6. Generar ACTA, ANEXO y ZIP.

La extraccion automatica siempre debe revisarse antes de generar documentos oficiales.

## Marcadores de Word

La generacion valida estos marcadores:

- ACTA: `[[SERVICE_SUMMARY]]`, `[[EQUIPMENT_SECTIONS]]`.
- ANEXO: `[[ANNEX_SECTIONS]]`.

## Catalogos de trabajos

Los textos aleatorios estables para la generacion se editan aqui:

- `app/document_content/minisplit/work_options.txt`
- `app/document_content/package/work_options.txt`

En paquetes, las lineas envueltas con `***` se tratan como grupo inseparable. Por ejemplo, si se selecciona una opcion TXV agrupada con filtro deshidratador, ambas se agregan juntas.

## Excel

La fase 4 exportara hojas normalizadas y hojas heredadas compatibles: `General`, `Lots`, `Equipment`, `Signatures`, `WorkCatalog`, `EquipmentWork`, `Review`, `Work` y `Report`.

## Pruebas

```bash
pytest
```

Las pruebas usan carpetas temporales unicas bajo `storage/test_runs`, desactivan la cache de pytest y excluyen `storage` del lint para evitar problemas de permisos en Windows con `AppData`, `.pytest_cache` o archivos generados.

## Privacidad

La aplicacion guarda documentos localmente en `storage/`, no llama APIs externas, no usa LLMs y no incluye analiticas. Si se despliega internamente, usa respaldos cifrados regulares para `storage/` y la base SQLite.

## Solucion de problemas

- Si una carga falla, revisa que el archivo sea `.docx` real y no `.docm`.
- Si `alembic` no encuentra la app, ejecuta los comandos desde la carpeta `document_app`.
- Si expones la app en red y no inicia, revisa que la autenticacion este habilitada.
