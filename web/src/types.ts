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
