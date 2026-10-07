# HKUST Canvas Workbench interface

## Direction

Operate mode. A wayfinding board for the user's courses: an anchored navigation rail, readable ruled course rows, consistent term columns and one clear route into each workspace. The design is code-led under the user's delegated implementation request.

Grounded candidates considered: library catalog, laboratory notebook, academic portal, working folders, research bibliography, campus wayfinding board, split file manager. The assigned sixth direction is campus wayfinding. Catalog challenges were considered as complete systems: dense Japanese modules are competitive on information density but weaker for first-run clarity; cassette cards, encoded record sleeves, vertical video, and botanical plates obscure the task and were declined. The split-flap concourse is competitive but its fixed character cells harm long course names. Its discipline of stable columns is retained without animation or metaphorical departure times. The catalog's density discipline is retained with scalable text and restrained gaps.

## Visual system

Cool paper (#e7ecef), lapis blue (#005a9c) navigation, actions, selection and keyboard focus, and near-black ink (#11191f). Red is reserved for errors and destructive actions. Secondary paper (#d8e0e5) separates controls from the working surface. Public Sans is self-hosted from the frontend dependency. Lucide line icons use a consistent stroke. No external fonts, gradients, illustration, decorative metrics or fake course totals.

Desktop uses a 224px navigation rail and a content field that fills the available width with balanced gutters. Course entries share aligned rows and substantial titles. Workspace uses Sources, Conversation and Study Studio panels. Two draggable dividers redistribute their widths while preserving usable minimums; arrow keys adjust them, double-click restores defaults, and the browser remembers proportions. Tablet puts Studio below the other panels; mobile collapses navigation to a top bar and stacks all panels. Dividers are hidden in stacked layouts. Source inspection uses a keyboard-accessible dialog; citations open indexed text and a canonical Canvas link.

## Interaction

Course row focus and hover reveal a quiet route-arrow translation. Dashboard courses and workspaces share a remembered list/card view preference. Canvas profile configuration appears inline on the dashboard and in full-width Settings. Create and rename forms are inline. Workspace deletion requires a deliberate second step and explains that Canvas is unaffected. Materials use directly selectable buttons for Quiz, Flashcards, Study guide, Word and Excel; difficulty is a three-step slider with a visible label. Studio accepts additional instructions and Word templates. Canvas actions use grouped buttons inside their disclosure; selecting one only opens its form. Chat controls share a row when the panel is wide and reflow within narrow panels. Chat content follows the panel boundary. Return and modifier-Return can exchange send/newline roles, with composition events excluded. Reduced motion removes transitions. All controls have visible focus, names and touch targets.

Source selection offers all/ready/category choices. Reading previews preserve Canvas paragraphs, headings, lists, tables and supported text styles, independently of overlapping retrieval chunks. Active embeds and automatic remote-media loads are excluded; the canonical Canvas link opens authenticated media. Uploaded text uses a continuous reading view. Storage explanations are concentrated in Settings, and provider sharing remains explicit at send/generate controls. The sidebar describes user control, without falsely promising that cloud-bound context never leaves the device.

## Scope truth

Source inventory never starts a download. Sync state and failed extraction are explicit. Chat and Studio disclose the selected provider and shared context; generation needs ready selected sources and a provider. Live Canvas actions can be used without a model. A separate human-confirm card shows account, target, recipients and content before a write. Course metadata and saved-work counts come from the API. Demonstration data belongs only in mocked tests.
