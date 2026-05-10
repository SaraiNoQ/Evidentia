# Parsing Design: PaperIR-first Canonical Pipeline

## 1. Goal

The parsing layer must produce canonical paper structure for AI review, not just raw text. The target output is:

```text
PDF -> parser ensemble -> PaperIR -> canonical markdown -> reviewer agents
```

`PaperIR` is the authoritative trace representation. `canonical_paper.md` is the primary text artifact for pure-text LLM review and downstream Markdown-first paper understanding.

## 2. Parser Profiles

### research_default

Default profile for internal research iteration.

- GROBID: metadata, abstract, section tree, references, citation contexts.
- Marker: main content flow, markdown/json blocks, equations, inline math, basic tables, images.
- pdffigures2: figure/table captions, numbering, image crops and caption-object binding.
- PyMuPDF: text-based PDF preflight, embedded image fallback, low-level debug extraction.

Marker is GPL/commercial-license sensitive. This profile is acceptable for internal research, but commercial self-hosting needs explicit licensing or replacement.

### commercial_safe

Commercial-friendly profile before productization.

- GROBID + Docling + pdffigures2 + PyMuPDF.
- Marker disabled unless explicitly enabled by the user.

### hard_case

Fallback profile for low-confidence parsing.

- research_default + Docling + Camelot + MinerU.
- Used for formula-heavy, table-heavy, multi-column or otherwise difficult documents.

## 3. PaperIR v0.2

PaperIR contains:

- `metadata`: title, authors, affiliations, keywords, venue, year, DOI.
- `abstract`: canonical abstract text.
- `sections`: canonical section tree.
- `blocks`: paragraphs, headings, equations and artifact references.
- `references`: structured bibliography records.
- `citations`: in-text citation contexts.
- `assets`: figures, tables, equations and extracted image assets.
- `parse_report`: confidence scores, parser sources and warnings.

The current implementation builds PaperIR v0.2 with the `research_default` parser ensemble: PyMuPDF preflight/fallback, GROBID skeleton extraction, Marker content parsing and pdffigures2 figure/table extraction.

## 4. Pipeline

### 4.1 Preflight

Use PyMuPDF to detect whether the PDF is text-based. If most pages have no extractable text, mark the parse report as `unsupported_scanned_pdf` and do not enter OCR fallback.

### 4.2 GROBID Skeleton Pass

Implemented source of truth for:

- title.
- authors.
- abstract.
- section headings.
- references.
- citation contexts.

### 4.3 Marker Content Pass

Implemented primary source for:

- body markdown.
- paragraphs.
- inline math.
- display equations.
- basic tables.
- image placeholders.

Marker must parse the full PDF for normal `quick_audit` and `local_full_audit` jobs because `canonical_paper.md` is the primary text input for downstream LLM understanding. Page-limited Marker runs are allowed only through explicit `max_pages` or environment-level smoke-test configuration, and must emit `marker_partial_page_parse:{parsed}/{total}` so truncated Markdown is never treated as a complete paper.

### 4.4 pdffigures2 Asset Pass

Implemented source for:

- figure/table labels.
- captions.
- cropped images.
- caption-object binding.

### 4.5 Fusion

Fusion rules:

- Use GROBID section tree as the canonical order when available.
- Fuzzy-align Marker/Docling headings into canonical sections.
- Attach paragraphs, equations, tables and figures to the nearest section.
- Deduplicate table/figure captions across parser sources.
- Preserve parser conflicts as warnings; never silently overwrite.

### 4.6 Rendering

The renderer produces:

- `canonical_paper.md`
- `paper_ir.json`
- `parse_report.json`
- future `assets/figures/*`
- future `assets/tables/*`

Renderer rules:

- title/authors/abstract first.
- sections in canonical order.
- tables rendered as HTML when available, otherwise markdown/cells.
- figures rendered with image references plus caption text.
- references rendered from structured GROBID records when available.

## 5. Parse Gates

Required parse gate signals:

- text-based PDF status.
- section coverage.
- reference coverage.
- table confidence.
- figure/caption alignment confidence.
- equation confidence.
- parser source coverage.
- parser conflict warnings.

Low-confidence parse results are allowed, but reviewer agents must see the warnings and should downgrade unsupported findings.

## 6. Current Implementation State

Implemented:

- PaperIR v0.2 schema.
- PyMuPDF fallback to PaperIR conversion.
- real GROBID TEI adapter for sections, references, citations, DOI and abstract fallback.
- real Marker adapter for recursive JSON block extraction into clean Markdown text.
- real pdffigures2 adapter for figure/table captions and cropped image assets.
- PaperIR fusion for parser source tracking, heading alignment, section repair and front-matter cleanup.
- canonical markdown renderer.
- `paper_ir.json`, `canonical_paper.md`, `parse_report.json` persistence.
- trace embedding of PaperIR.
- CPFL.pdf smoke test: GROBID, Marker and pdffigures2 all connected; output Markdown contains no Marker `<content-ref>` placeholders.

Not implemented yet:

- Docling structure checker.
- Camelot table repair.
- MinerU hard-case fallback.
- OCR fallback.

Next integration step:

- Treat `canonical_paper.md` as the primary LLM input for Markdown-first paper understanding.
- Keep `PaperIR` in `trace.json` for parser provenance, section map, references, figures, tables, warnings and evidence anchors.

## 7. External Tool Notes

- GROBID is the metadata/reference/section skeleton authority.
- Marker is the research-default content parser and carries license risk.
- Docling is the commercial-safe structure parser and validator.
- pdffigures2 owns figure/table caption-object binding.
- Camelot is table repair only, not a full document parser.
- PyMuPDF remains the low-level fallback and preflight tool.
