<div align="center">

<img src="docs/logo.svg?v=2" alt="Your AI Lawyer" width="420"/>

</div>

<div align="center">

[English](README.md) · **Español**

[![Licencia: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue)](https://www.python.org/downloads/)
[![uv](https://img.shields.io/badge/gestionado%20con-uv-blueviolet)](https://github.com/astral-sh/uv)
[![Claude Code](https://img.shields.io/badge/interfaz-Claude%20Code-orange)](https://claude.ai/code)

**Base de conocimiento jurídico multipaís — legislación en bruto compilada en un grafo de conocimiento consultable mediante comandos slash de Claude Code**

[Comandos Slash](#comandos-slash) • [Arquitectura](#arquitectura) • [Añadir Países](#añadir-un-nuevo-país) • [Seguimiento](#seguimiento) • [Issues](https://github.com/arnabdeypolimi/your-ai-lawyer/issues)

</div>

---

Las leyes originales de cada país viven como submódulos de git. Claude Code lee cada archivo de ley directamente y lo compila en un grafo de conocimiento compatible con Obsidian, con resúmenes, wikilinks, índices de conceptos y referencias cruzadas — sin necesidad de clave de API externa. Un almacén vectorial local de ChromaDB impulsa la búsqueda semántica y las respuestas RAG con citas en línea al texto original de la ley.

<div align="center">

![Grafo de conocimiento — 10 leyes de Cataluña compiladas y sus nodos de concepto en Obsidian](docs/knowledge-graph.png)

*Vista de grafo en Obsidian de las primeras 10 leyes compiladas de Cataluña (nodos `BOE-A-*`) y sus archivos de índice de conceptos compartidos.*

</div>

---


## Características

- Compila cualquier país o región de forma aislada — `/compile es-ct` solo para Cataluña, `/compile es` para toda España
- La salida del grafo de conocimiento es Markdown válido de Obsidian con `[[wikilinks]]`, nodos de concepto y referencias cruzadas
- Índice ChromaDB de dos colecciones (resúmenes compilados + fragmentos de artículos originales) para una recuperación de alta precisión
- Seguimiento mediante manifiesto + índice — la recompilación omite archivos sin cambios; `index.json` y `compile.log` registran cada ejecución
- `/lint` comprueba errores de compilación, notas huérfanas, wikilinks rotos y archivos no rastreados
- `/qa` responde preguntas con citas en línea (`[BOE-A-XXXX-XXXXX, Art. N]`) — sin necesidad de clave API
- Extensible a cualquier país: añade un submódulo, ejecuta `/compile`, listo

---

## Inicio Rápido

### Instalación

```bash
git clone --recurse-submodules https://github.com/arnabdeypolimi/your-ai-lawyer.git
cd your-ai-lawyer
uv sync
```

Requiere [uv](https://github.com/astral-sh/uv) y [Claude Code](https://claude.ai/code).

### Abrir en Claude Code

```bash
claude .
```

### Elige tu idioma de salida (configuración inicial)

```bash
/setup            # pregunta por un idioma
/setup es         # o establécelo directamente
```

Códigos soportados: `en` (inglés), `es` (español), `ca` (catalán), `fr` (francés), `it` (italiano), `de` (alemán), `pt` (portugués) — o cualquier código BCP-47 (se pasa directamente al modelo).

La configuración se guarda en `.claude/settings.json` bajo `env.OUTPUT_LANGUAGE` y se aplica a todas las ejecuciones futuras de `/compile` y respuestas de `/qa`. Las notas ya compiladas **no** se traducen retroactivamente; ejecuta `/compile <jurisdicción> --force` para volver a localizarlas.

### Compilar leyes

```bash
/compile es-ct --limit 10        # Cataluña — primeras 10 leyes (prueba)
/compile es --rank constitucion  # España — solo leyes constitucionales
/compile es                      # España — las 12 000+ leyes (en lotes)
```

### Construir el índice de búsqueda

```bash
/index                              # indexa España (por defecto)
/index --country es --compiled-only
```

### Consultar

```bash
/qa ¿Cuáles son los derechos de vivienda de los inquilinos en España?
/qa ¿Tiene Cataluña sus propias leyes de protección de datos?
/search derecho a la educación --country es --n 10
```

### Comprobar el estado

```bash
/lint                            # revisión completa
/lint --jurisdiction es-ct       # limitado a Cataluña
/lint --broken-links             # también escanea wikilinks rotos (más lento)
```

---

## Comandos Slash

| Comando | Descripción |
|---------|-------------|
| `/setup [<código-idioma>]` | Selecciona idioma de salida para notas compiladas y `/qa` |
| `/compile <jurisdicción> [--limit N] [--rank R] [--force]` | Compila leyes originales en el grafo de conocimiento |
| `/index [--country X] [--compiled-only] [--raw-only]` | Construye / actualiza el índice vectorial ChromaDB |
| `/search <consulta> [--country X] [--rank R] [--n N]` | Búsqueda semántica con resultados ordenados |
| `/qa <pregunta>` | Respuesta RAG con citas en línea |
| `/lint [--jurisdiction X] [--broken-links]` | Revisión de salud de la base de conocimiento |

Jurisdicciones soportadas para España: `es` (nacional), `es-ct`, `es-md`, `es-an`, `es-pv`, `es-ga`, `es-vc`, `es-ib`, `es-ar`, `es-cn`, `es-cl`, `es-cm`, `es-cb`, `es-as`, `es-ri`, `es-nc`, `es-mc`.

---

## Arquitectura

```
your-ai-lawyer/
├── legalize-es/              # Leyes originales de España (submódulo git, 12K+ archivos)
├── knowledge/                # Bóveda Obsidian compilada
│   ├── laws/es/              # Un .md por ley: resumen, disposiciones, wikilinks
│   ├── concepts/             # Archivos de índice de conceptos con backlinks
│   └── jurisdictions/        # Notas de resumen por país
├── data/
│   ├── index.json            # Estado de compilación por ley
│   ├── compile.log           # Historial de ejecuciones (NDJSON)
│   ├── manifest.json         # Hashes MD5 para detección de cambios
│   └── chroma/               # Almacén vectorial ChromaDB (gitignored)
└── src/
    ├── compiler/             # parser, extractor, batch, tracker, lint
    ├── indexer/              # pipeline de embeddings ChromaDB
    └── query/                # búsqueda semántica
```

### Pipeline de compilación

```
legalize-<país>/
  markdown original + YAML frontmatter
          │
          ▼  /compile (Claude Code lee y escribe directamente)
          │   list_files.py  →  lista archivos que necesitan compilación
          │   tracker.py     →  registra resultado en index.json + compile.log
          │
knowledge/laws/<país>/
  notas compiladas con [[wikilinks]]
          │
          ▼  /index (embeddings ONNX locales — sin clave API)
          │
data/chroma/
  colección compiled + colección raw_chunks
          │
          ▼  /qa o /search
  citas: [BOE-A-XXXX-XXXXX, Art. N]
```

### Formato de nota compilada

Cada `knowledge/laws/es/<identifier>.md` contiene:

```yaml
---
identifier: BOE-A-1978-31229
title: "Constitución Española"
country: es
jurisdiction: es
rank: constitucion
status: in_force
compiled_at: 2026-04-21
---
```

Seguido de: **Resumen**, **Disposiciones clave**, **Referencias cruzadas** (`[[wikilinks]]`), **Deroga**, **Desarrolla**, **Conceptos**, y un enlace al archivo original. La carpeta `knowledge/` es una bóveda Obsidian válida.

---

## Seguimiento

Tres archivos en `data/` rastrean el estado de compilación:

| Archivo | Contenido |
|---------|-----------|
| `manifest.json` | `{ ruta_original: hash_md5 }` — omite archivos sin cambios al recompilar |
| `index.json` | Registro por ley: `status`, `compiled_at`, `note_path`, `error` |
| `compile.log` | Historial NDJSON: marca temporal, jurisdicción, conteos, IDs con error |

Consulta el estado directamente:

```bash
uv run python -m src.compiler.tracker status
uv run python -m src.compiler.tracker status --jurisdiction es-ct
uv run python -m src.compiler.tracker log --n 20
```

---

## Añadir un Nuevo País

Todos los datos de los países provienen de la organización [legalize-dev](https://github.com/legalize-dev) — cada repo es la legislación de un país como archivos Markdown con historial de git.

### Paso 1 — Añadir el submódulo

Reemplaza `XX` con el código del país (por ejemplo, `fr`, `de`, `us`):

```bash
git submodule add https://github.com/legalize-dev/legalize-XX.git legalize-XX
git submodule update --init legalize-XX
```

### Paso 2 — Compilar en Claude Code

```bash
claude .
```

Luego ejecuta:

```bash
/compile XX --limit 20    # prueba — primeras 20 leyes
/compile XX               # ejecución completa (usa --limit N y repite en lotes para países grandes)
```

### Paso 3 — Construir el índice de búsqueda

```bash
/index --country XX
```

### Paso 4 — Consultar

```bash
/qa ¿Cuáles son los derechos laborales en Francia?
/search protección de datos --country fr
```

### Consejos para países grandes

EE. UU. (`legalize-us`) tiene 60 000+ secciones y Portugal (`legalize-pt`) tiene 109 000+ normas. Compila por lotes según el rango:

```bash
/compile us --rank statute --limit 50
/compile pt --rank lei --limit 50
```

Consulta el progreso entre ejecuciones:

```bash
uv run python -m src.compiler.tracker status --jurisdiction us
```

---

## Países Disponibles

Los 28 países están disponibles en [github.com/legalize-dev](https://github.com/legalize-dev). Añade cualquiera como submódulo usando las instrucciones anteriores.

| País | Código | Submódulo | Leyes | Fuente |
|------|--------|-----------|-------|--------|
| 🇦🇩 Andorra | `ad` | `legalize-ad` | — | BOPA |
| 🇦🇷 Argentina | `ar` | `legalize-ar` | — | Infoleg |
| 🇦🇹 Austria | `at` | `legalize-at` | — | RIS |
| 🇧🇪 Bélgica | `be` | `legalize-be` | — | Justel |
| 🇨🇱 Chile | `cl` | `legalize-cl` | — | BCN / Ley Chile |
| 🇨🇿 República Checa | `cz` | `legalize-cz` | — | ⚠️ En desarrollo |
| 🇩🇰 Dinamarca | `dk` | `legalize-dk` | — | retsinformation.dk |
| 🇪🇪 Estonia | `ee` | `legalize-ee` | — | Riigi Teataja |
| 🇫🇮 Finlandia | `fi` | `legalize-fi` | — | Finlex |
| 🇫🇷 Francia | `fr` | `legalize-fr` | — | Légifrance |
| 🇩🇪 Alemania | `de` | `legalize-de` | — | gesetze-im-internet.de |
| 🇬🇷 Grecia | `gr` | `legalize-gr` | — | ΦΕΚ Α' |
| 🇮🇪 Irlanda | `ie` | `legalize-ie` | — | legislation.ie |
| 🇮🇹 Italia | `it` | `legalize-it` | — | Normattiva |
| 🇰🇷 Corea del Sur | `kr` | `legalize-kr` | — | 국가법령정보센터 |
| 🇱🇻 Letonia | `lv` | `legalize-lv` | — | likumi.lv |
| 🇱🇹 Lituania | `lt` | `legalize-lt` | — | TAR / data.gov.lt |
| 🇱🇺 Luxemburgo | `lu` | `legalize-lu` | — | legilux.lu |
| 🇳🇱 Países Bajos | `nl` | `legalize-nl` | — | Basis Wetten Bestand |
| 🇳🇴 Noruega | `no` | `legalize-no` | — | Lovdata (NLOD 2.0) |
| 🇵🇱 Polonia | `pl` | `legalize-pl` | — | Sejm / Dziennik Ustaw |
| 🇵🇹 Portugal | `pt` | `legalize-pt` | 109K+ | Diário da República |
| 🇸🇰 Eslovaquia | `sk` | `legalize-sk` | — | Slov-Lex |
| 🇪🇸 España | `es` | `legalize-es` ✅ | 12K+ | BOE |
| 🇸🇪 Suecia | `se` | `legalize-se` | — | riksdagen.se |
| 🇺🇦 Ucrania | `ua` | `legalize-ua` | — | Verkhovna Rada |
| 🇬🇧 Reino Unido | `gb` | — | — | Próximamente |
| 🇺🇸 Estados Unidos | `us` | `legalize-us` | 60K+ | US Code |
| 🇺🇾 Uruguay | `uy` | `legalize-uy` | — | IMPO |

✅ = ya añadido como submódulo · ⚠️ = en desarrollo activo, la estructura puede cambiar

---

## Contribuir

Abre un [issue](https://github.com/arnabdeypolimi/your-ai-lawyer/issues) para discutir nuevos submódulos de países, mejoras del pipeline o mejoras de consulta, y luego envía un PR.

## Agradecimientos

Los datos de legislación original son proporcionados por [legalize-dev](https://github.com/legalize-dev), una organización de código abierto que publica textos legales oficiales gubernamentales como repositorios Markdown estructurados. Cada submódulo de país se mantiene de forma independiente bajo su propia licencia — consulta el repositorio correspondiente para los términos. Este proyecto no sería posible sin su trabajo de recopilación, limpieza y versionado de fuentes legales de dominio público a través de 28 países.

## Condiciones de Uso

Este proyecto está destinado **únicamente a uso personal y no comercial**.

La información compilada por esta herramienta no constituye asesoramiento legal. El/los mantenedor(es) de este proyecto no son abogados y no aceptan responsabilidad alguna por la exactitud, completitud o idoneidad de ningún resultado compilado, resultado de búsqueda o respuesta generada. Consulta siempre a un profesional del derecho cualificado para asesoramiento sobre tu situación específica.

Al usar este proyecto aceptas que:
- No lo utilizarás con fines comerciales sin obtener las licencias apropiadas para todos los textos legales subyacentes
- El/los mantenedor(es) no son responsables de daños, pérdidas o consecuencias legales derivadas de la confianza en esta herramienta
- Los textos legales pueden estar desactualizados, incompletos o compilados incorrectamente — verifica con fuentes oficiales del gobierno antes de actuar según cualquier información

## Licencia

MIT. Los textos legales de los submódulos son de dominio público (publicaciones oficiales gubernamentales). Consulta cada submódulo para sus propios términos de licencia.
