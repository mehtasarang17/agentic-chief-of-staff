// Type definitions for the Chief of Staff application

export interface User {
  id: string
  email: string
  name: string
  preferences: Record<string, any>
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agentName?: string
  thoughts?: string[]
  toolCalls?: ToolCall[]
  sources?: Source[]
  timestamp: Date
  isStreaming?: boolean
}

export interface ToolCall {
  tool: string
  action: string
  params?: Record<string, any>
}

export interface Source {
  document_id: string
  filename: string
  file_type: string
  similarity: number
}

export interface Conversation {
  id: string
  title: string
  summary?: string
  lastMessage?: string
  messageCount: number
  createdAt: Date
  updatedAt: Date
}

export interface Agent {
  id: string
  name: string
  displayName: string
  description: string
  agentType: 'master' | 'worker'
  capabilities: string[]
  isActive: boolean
  status: 'idle' | 'thinking' | 'working'
  memoryCount?: number
}

export interface Document {
  id: string
  filename: string
  originalFilename: string
  fileType: string
  fileSize: number
  status: 'pending' | 'processing' | 'completed' | 'failed'
  chunkCount: number
  createdAt: Date
}

export interface ChatRequest {
  message: string
  conversationId?: string
  useRag?: boolean
  context?: Record<string, any>
}

export interface ChatResponse {
  conversationId: string
  messageId: string
  response: string
  agent: string
  thoughts: string[]
  toolCalls: ToolCall[]
  isFinal: boolean
  needsClarification: boolean
  clarificationQuestion?: string
  sources: Source[]
}

export interface AgentStats {
  agentId: string
  agentName: string
  displayName: string
  agentType: string
  isActive: boolean
  memoryBreakdown: Record<string, number>
  totalMemories: number
}

export interface PaginationInfo {
  page: number
  perPage: number
  total: number
  totalPages: number
}

export interface ApiError {
  error: string
  details?: string
}
