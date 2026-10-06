# HKUST Canvas Workbench

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

Python with an additive FastAPI web extra; React, TypeScript and Vite. The existing setuptools package, Canvas CLI and MCP server remain the foundation.

## Users

HKUST Canvas users organizing their course materials on their own computer.

## Product Purpose

A local study workspace with replaceable model providers and continued access through MCP and the CLI. The first implementation is Phase A: a course dashboard, persistent course/custom workspaces and a Settings shell.

## Positioning

One HKUST Chrome-session Canvas integration shared by the web UI, CLI and MCP. No Canvas PAT, cloud hosting or consumer AI session scraping.

## Operating Context

The app runs as a native Python process on loopback. Existing Chrome profile selection and authentication settings remain authoritative. Runtime data belongs outside the repository.

## Capabilities and Constraints

Phase A has no source synchronization, indexing, chat or model configuration. Later phases add these after the foundation passes its checks. Canvas writes retain the existing server-side confirmation system. Provider credentials and Canvas cookies never belong in browser JavaScript or local workspace records.

## Brand Commitments

Product name: HKUST Canvas Workbench. Use an original visual identity rather than reproducing HKLearn or NotebookLM. The user delegated implementation choices and explicitly requested no questions during this work.

## Evidence on Hand

The existing README, CanvasClient and registered tools establish the integration. Automated examples use synthetic course data. Real personal Canvas results must never be committed.

## Product Principles

- Keep Canvas authentication and handlers shared.
- Make local ownership and source/model boundaries visible.
- Preserve existing users' CLI and MCP behavior.
- Show unavailable features honestly until they are implemented.
