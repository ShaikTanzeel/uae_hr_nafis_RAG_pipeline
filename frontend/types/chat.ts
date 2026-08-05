// types/chat.ts — TypeScript interfaces mirroring src/schemas.py Pydantic models

export interface Citation {
  article_number: string;
  source_document: string;
}

export interface ChatMessage {
  role: "user" | "assistant" | "tool";
  content?: string | null;
  tool_calls?: ToolCall[] | null;
  tool_call_id?: string;
  citations?: Citation[];
}

export interface ToolCall {
  id: string;
  type: "function";
  function: {
    name: string;
    arguments: string;
  };
}

export interface ChatRequest {
  query: string;
  history: ChatMessage[];
}

export interface ChatResponse {
  answer: string;
  citations: Citation[];
  articles_used: string[];
  confidence: number;
  cannot_verify: boolean;
  injection_blocked: boolean;
  retrieved_context: string;
  history: ChatMessage[];
}

export interface HealthResponse {
  status: "ok" | "degraded";
  qdrant_connected: boolean;
  collection_name?: string;
  vector_count?: number;
  model: string;
  embedding_model: string;
}

export interface LawDocument {
  id: string;
  title: string;
  description: string;
  short: string;
}

// UI display model — enriched version of ChatMessage used in the chat view
export interface DisplayMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  retrieved_context?: string;
  tool_expression?: string;
  tool_result?: string;
  cannot_verify?: boolean;
  confidence?: number;
  timestamp: Date;
}
