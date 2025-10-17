// Config types
export interface AppConfig {
  id: number;
  business_name?: string;
  tagline?: string;
  hero_text?: string;
  hero_image_url?: string;
  logo_url?: string;
  lakera_enabled: boolean;
  lakera_blocking_mode: boolean;
  lakera_project_id?: string;
  openai_model: string;
  temperature: number;
  system_prompt?: string;
  openai_api_key?: string;
  lakera_api_key?: string;
  created_at: string;
  updated_at: string;
}

export interface AppConfigUpdate {
  business_name?: string;
  tagline?: string;
  hero_text?: string;
  hero_image_url?: string;
  logo_url?: string;
  lakera_enabled: boolean;
  lakera_blocking_mode: boolean;
  openai_model: string;
  temperature: number;
  system_prompt?: string;
  openai_api_key?: string;
  lakera_api_key?: string;
  lakera_project_id?: string;
}

// Chat types
export interface ChatRequest {
  message: string;
  session_id?: string;
}

export interface ChatResponse {
  response: string;
  lakera?: any;
  tool_traces?: any[];
  citations?: any[];
}

// RAG types
export interface RagGenerateRequest {
  industry: string;
  seed_prompt: string;
  preview_only: boolean;
}

export interface RagGenerateResponse {
  markdown: string;
  ingested: boolean;
}

export interface RagSearchResponse {
  chunks: any[];
}

// Tool types
export interface Tool {
  id: number;
  name: string;
  description?: string;
  endpoint?: string;
  type: string;
  enabled: boolean;
  config_json?: any;
  created_at: string;
  updated_at: string;
}

export interface ToolCreate {
  name: string;
  description?: string;
  endpoint?: string;
  type: string;
  enabled: boolean;
  config_json?: any;
}

export interface ToolUpdate extends ToolCreate {}

// Lakera types
export interface LakeraDetectorResult {
  project_id?: string;
  policy_id?: string;
  detector_id?: string;
  detector_type?: string;
  detected: boolean;
  message_id?: number;
}

export interface LakeraResult {
  payload: any[];
  flagged: boolean;
  dev_info?: any;
  metadata?: any;
  breakdown: LakeraDetectorResult[];
}

// Chat message types
export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  tool_traces?: any[];
  lakera?: any;
}

// Demo Prompt types
export interface DemoPrompt {
  id: number;
  title: string;
  content: string;
  category: string;
  tags: string[];
  is_malicious: boolean;
  usage_count: number;
  created_at: string;
  updated_at: string;
}

export interface DemoPromptCreate {
  title: string;
  content: string;
  category: string;
  tags: string[];
  is_malicious: boolean;
}

export interface DemoPromptUpdate extends DemoPromptCreate {}

export interface DemoPromptSuggestion {
  text: string;
  full_content: string;
  title: string;
  category: string;
  is_malicious: boolean;
}

export interface DemoPromptSearchResponse {
  prompts: DemoPrompt[];
  suggestions: DemoPromptSuggestion[];
}

// Detector labels mapping
export const DETECTOR_LABELS: Record<string, string> = {
  "prompt_attack": "Prompt Attack",
  "unknown_links": "Unknown Links",
  "moderated_content/crime": "Crime",
  "moderated_content/hate": "Hate",
  "moderated_content/profanity": "Profanity",
  "moderated_content/sexual": "Sexual Content",
  "moderated_content/violence": "Violence",
  "moderated_content/weapons": "Weapons",
  "pii/address": "PII: Address",
  "pii/credit_card": "PII: Credit Card",
  "pii/iban_code": "PII: IBAN",
  "pii/ip_address": "PII: IP Address",
  "pii/us_social_security_number": "PII: SSN"
};

