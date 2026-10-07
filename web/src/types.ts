export type Course = {
  id: string;
  name: string;
  course_code: string | null;
  term_name: string | null;
  canvas_url: string;
};
export type Workspace = {
  id: string;
  kind: "custom" | "canvas_course";
  canvas_course_id: string | null;
  title: string;
  description: string;
  course_code: string | null;
  term_name: string | null;
  created_at: string;
  updated_at: string;
  last_sync_at: string | null;
};
export type CanvasStatus = {
  auth_verified: boolean;
  auth_status: string;
  profile_name: string | null;
  message: string;
};
export type Settings = {
  phase: string;
  canvas_url: string;
  profile_name: string | null;
  storage: string;
  schema_version: number;
  mcp_command: string;
  providers_available: boolean;
};

export type Source = {
  id: string;
  workspace_id: string;
  source_key: string;
  kind: string;
  title: string;
  canvas_url: string | null;
  status: string;
  mime_type: string | null;
  last_sync_at: string | null;
  remote_updated_at: string | null;
  error_message: string | null;
  error_code: string | null;
  metadata: {
    filename?: string;
    size?: number;
    external_url?: string;
    items?: { title: string; type: string; source_key?: string }[];
  };
};
export type Chunk = {
  id: string;
  source_id: string;
  text: string;
  locator: Record<string, string | number>;
  source_title?: string;
  canvas_url?: string;
};
export type Citation = {
  chunk_id: string;
  source_id: string;
  title: string;
  canvas_url: string | null;
  locator: Record<string, string | number>;
  excerpt: string;
};
export type Provider = {
  id: string;
  name: string;
  kind: "openai" | "anthropic" | "compatible" | "codex" | "claude_code";
  model: string;
  base_url: string;
  has_key: boolean;
  credential_store: string;
  capabilities: {
    streaming: boolean;
    native_tools: boolean;
    structured_output: boolean;
  };
};
export type Message = {
  id: string;
  role: string;
  content: string;
  status: string;
  citations: Citation[];
  provider_id: string | null;
  model: string | null;
};
export type Conversation = { id: string; title: string; messages?: Message[] };
export type Preview = {
  id: string;
  tool: string;
  account: Record<string, unknown>;
  target: Record<string, unknown>;
  payload: Record<string, unknown>;
  expires_at: string;
  status: string;
};
export type ArtifactItem = {
  type?: string;
  question?: string;
  choices?: string[];
  answer_index?: number;
  explanation?: string;
  front?: string;
  back?: string;
  heading?: string;
  body?: string;
  citations: string[];
  cells?: string[];
};
export type Artifact = {
  id: string;
  kind: "quiz" | "flashcards" | "study_guide" | "document" | "spreadsheet";
  title: string;
  content: {
    title: string;
    questions?: ArtifactItem[];
    cards?: ArtifactItem[];
    sections?: ArtifactItem[];
    template?: string;
    columns?: string[];
    rows?: ArtifactItem[];
  };
  provenance: {
    citations: Citation[];
    model: string;
    provider_name: string;
    created_at: string;
    source_ids: string[];
    prompt_version: string;
  };
};
export type Note = {
  id: string;
  title: string;
  content: string;
  provenance: { citations?: Citation[] };
  updated_at: string;
};
