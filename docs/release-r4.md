# R4: public documentation and screenshots

README now starts with Your Canvas. Your AI., a synthetic workspace image and macOS download. It covers setup without development tools, safety, provider/MCP distinctions, actual compatibility/verification, ad-hoc signing, troubleshooting, separate app/data/credential removal and future workspace MCP access. Detailed legacy installation/CLI guidance is preserved in development.md; releasing.md documents builds and manual checks. Original-project and vishalsachdev acknowledgements remain.

HKLearn/HKGAI V3 wording is supported by the official HKGAI product page. No unverified DeepSeek ancestry claim is published. NotebookLM-like is a comparison of the described sources/chat/study-output workflow, not an implementation or copying allegation.

Five public PNGs were generated from isolated Playwright API fixtures and visually checked: dashboard with saved workspace, course workspace with grounded answer/quiz, provider choices, citation inspection and write preview. All courses, accounts and responses are synthetic. No personal screenshot, real Canvas write or paid inference was used. Browser screenshot paths now work on Linux as well as macOS.

Validation: **14 Playwright flows passed**, followed by the changed screenshot flow passing at its revised viewport. Authored local Markdown links resolve; diff whitespace checks pass. Runtime code is unchanged; Python remains **566 passing** and frontend **30 passing** from prior phases. No migration/compatibility change.

Exact changed files (12):

```text
MANIFEST.in
README.md
SECURITY.md
docs/development.md
docs/images/citation.png
docs/images/dashboard.png
docs/images/providers.png
docs/images/workspace.png
docs/images/write-preview.png
docs/release-r4.md
docs/releasing.md
web/e2e/workbench.spec.ts
```
