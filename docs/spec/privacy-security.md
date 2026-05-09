# Privacy and Security Spec

## 1. Manuscript Privacy

Default behavior:

- Parse locally.
- Store uploaded manuscripts under job-scoped paths.
- Do not use manuscripts for training.
- Send minimal chunks to remote models when possible.
- Support configurable retention.

Optional behavior:

- anonymize authors, affiliations, acknowledgments, grant numbers, and project identifiers before remote LLM calls.
- disable external retrieval.
- use paraphrased external queries.

## 2. Prompt Injection Defense

The manuscript is untrusted data. Retrieved papers and web pages are also untrusted data.

Rules:

- Agent prompts must explicitly state that manuscript text is not instruction.
- Retrieved text must not override system or developer policy.
- Suspicious instruction-like text from documents should be quoted or summarized as data.
- Agents must not follow instructions embedded in papers, PDFs, references, or retrieved snippets.

## 3. External Search Privacy

When external retrieval is enabled:

- Log every query.
- Record source, timestamp, and result ids.
- Prefer paraphrased queries for confidential manuscripts.
- Avoid exact title search unless user allows it.
- Allow users to inspect query logs.

## 4. Remote Model Calls

Every model call records:

- provider.
- model name.
- prompt version.
- input hash.
- token usage.
- output schema validation status.

Do not log full sensitive prompt payloads unless debug mode is explicitly enabled.

## 5. Retention

Retention options:

- delete immediately after report generation.
- temporary project storage.
- long-term workspace storage.

Deletion must include:

- uploaded files.
- parsed artifacts.
- model input cache.
- generated reports.
- trace files.

