const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:9001'

export interface ChatRequest {
  message: string
  conversation_id?: string
  use_rag?: boolean
  context?: Record<string, any>
}

export interface ChatResponse {
  conversation_id: string
  message_id: string
  response: string
  agent: string
  thoughts: string[]
  tool_calls: any[]
  is_final: boolean
  needs_clarification: boolean
  clarification_question?: string
  sources: any[]
}

export interface ConversationResponse {
  id: string
  title: string
  summary?: string
  message_count: number
  last_message?: string
  created_at: string
  updated_at: string
}

export interface AgentResponse {
  id: string
  name: string
  display_name: string
  description: string
  capabilities: string[]
  is_active: boolean
}

class ApiClient {
  private baseUrl: string

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`
    const response = await fetch(url, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options.headers,
      },
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.error || `API Error: ${response.status}`)
    }

    return response.json()
  }

  // Chat endpoints
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    return this.request<ChatResponse>('/api/chat/message', {
      method: 'POST',
      body: JSON.stringify(request),
    })
  }

  // Conversation endpoints
  async getConversations(
    page = 1,
    perPage = 20
  ): Promise<{ conversations: ConversationResponse[]; pagination: any }> {
    return this.request(`/api/conversations?page=${page}&per_page=${perPage}`)
  }

  async getConversation(id: string): Promise<ConversationResponse & { messages: any[] }> {
    return this.request(`/api/conversations/${id}`)
  }

  async createConversation(title?: string): Promise<ConversationResponse> {
    return this.request('/api/conversations', {
      method: 'POST',
      body: JSON.stringify({ title }),
    })
  }

  async deleteConversation(id: string): Promise<void> {
    return this.request(`/api/conversations/${id}`, {
      method: 'DELETE',
    })
  }

  // Agent endpoints
  async getAgents(): Promise<{ agents: AgentResponse[] }> {
    return this.request('/api/agents')
  }

  async getAgentStats(): Promise<any> {
    return this.request('/api/agents/stats')
  }

  // Document endpoints
  async uploadDocument(file: File): Promise<any> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await fetch(`${this.baseUrl}/api/documents`, {
      method: 'POST',
      body: formData,
    })

    if (!response.ok) {
      const error = await response.json().catch(() => ({}))
      throw new Error(error.error || 'Upload failed')
    }

    return response.json()
  }

  async getDocuments(page = 1, perPage = 20): Promise<any> {
    return this.request(`/api/documents?page=${page}&per_page=${perPage}`)
  }

  async searchDocuments(query: string): Promise<any> {
    return this.request('/api/documents/search', {
      method: 'POST',
      body: JSON.stringify({ query }),
    })
  }

  // Health check
  async healthCheck(): Promise<{ status: string }> {
    return this.request('/health')
  }
}

export const api = new ApiClient(API_URL)
