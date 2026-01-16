import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  agentName?: string
  thoughts?: string[]
  toolCalls?: any[]
  sources?: any[]
  agentSteps?: any[]
  timestamp: Date
  isStreaming?: boolean
}

export interface Conversation {
  id: string
  title: string
  lastMessage?: string
  updatedAt: Date
  messageCount: number
}

export interface Agent {
  id: string
  name: string
  displayName: string
  description: string
  capabilities: string[]
  isActive: boolean
  status: 'idle' | 'thinking' | 'working'
}

interface ConversationState {
  conversations: Conversation[]
  currentConversationId: string | null
  messages: Message[]
  isLoading: boolean
  isStreaming: boolean
  activeAgent: string | null
  agents: Agent[]
  documentIds: string[]

  // Actions
  setConversations: (conversations: Conversation[]) => void
  addConversation: (conversation: Conversation) => void
  setCurrentConversation: (id: string | null) => void
  setMessages: (messages: Message[]) => void
  addMessage: (message: Message) => void
  updateMessage: (id: string, updates: Partial<Message>) => void
  setLoading: (loading: boolean) => void
  setStreaming: (streaming: boolean) => void
  setActiveAgent: (agent: string | null) => void
  setAgents: (agents: Agent[]) => void
  updateAgentStatus: (name: string, status: Agent['status']) => void
  clearMessages: () => void
  deleteConversation: (id: string) => void
  addDocumentId: (id: string) => void
  clearDocumentIds: () => void
}

export const useConversationStore = create<ConversationState>()(
  persist(
    (set, get) => ({
      conversations: [],
      currentConversationId: null,
      messages: [],
      isLoading: false,
      isStreaming: false,
      activeAgent: null,
      documentIds: [],
      agents: [
        {
          id: '1',
          name: 'orchestrator',
          displayName: 'Chief of Staff',
          description: 'Master orchestrator that coordinates all agents',
          capabilities: ['Task Analysis', 'Delegation', 'Coordination'],
          isActive: true,
          status: 'idle'
        },
        {
          id: '2',
          name: 'calendar',
          displayName: 'Calendar Manager',
          description: 'Handles schedules, meetings, and appointments',
          capabilities: ['Scheduling', 'Reminders', 'Time Management'],
          isActive: true,
          status: 'idle'
        },
        {
          id: '3',
          name: 'email',
          displayName: 'Email Manager',
          description: 'Manages email composition and communication',
          capabilities: ['Drafting', 'Summarization', 'Prioritization'],
          isActive: true,
          status: 'idle'
        },
        {
          id: '4',
          name: 'research',
          displayName: 'Research Analyst',
          description: 'Conducts research and provides insights',
          capabilities: ['Research', 'Analysis', 'Reports'],
          isActive: true,
          status: 'idle'
        },
        {
          id: '5',
          name: 'task',
          displayName: 'Task Manager',
          description: 'Manages tasks, projects, and deadlines',
          capabilities: ['Task Tracking', 'Project Management', 'Priorities'],
          isActive: true,
          status: 'idle'
        },
        {
          id: '6',
          name: 'analytics',
          displayName: 'Analytics Expert',
          description: 'Provides data analysis and business intelligence',
          capabilities: ['Data Analysis', 'KPIs', 'Trends'],
          isActive: true,
          status: 'idle'
        },
        {
          id: '7',
          name: 'pdf',
          displayName: 'PDF Export',
          description: 'Exports the chat transcript as a PDF',
          capabilities: ['PDF Export', 'Transcript Download'],
          isActive: true,
          status: 'idle'
        }
      ],

      setConversations: (conversations) => set({ conversations }),
      addConversation: (conversation) =>
        set((state) => ({
          conversations: [conversation, ...state.conversations]
        })),
      setCurrentConversation: (id) => set({ currentConversationId: id }),
      setMessages: (messages) => set({ messages }),
      addMessage: (message) =>
        set((state) => ({
          messages: [...state.messages, message]
        })),
      updateMessage: (id, updates) =>
        set((state) => ({
          messages: state.messages.map((m) =>
            m.id === id ? { ...m, ...updates } : m
          )
        })),
      setLoading: (isLoading) => set({ isLoading }),
      setStreaming: (isStreaming) => set({ isStreaming }),
      setActiveAgent: (activeAgent) => set({ activeAgent }),
      setAgents: (agents) => set({ agents }),
      updateAgentStatus: (name, status) =>
        set((state) => ({
          agents: state.agents.map((a) =>
            a.name === name ? { ...a, status } : a
          )
        })),
      addDocumentId: (id) =>
        set((state) => ({
          documentIds: state.documentIds.includes(id)
            ? state.documentIds
            : [...state.documentIds, id]
        })),
      clearDocumentIds: () => set({ documentIds: [] }),
      clearMessages: () => set({ messages: [], currentConversationId: null }),
      deleteConversation: (id) =>
        set((state) => ({
          conversations: state.conversations.filter((c) => c.id !== id),
          currentConversationId:
            state.currentConversationId === id
              ? null
              : state.currentConversationId,
          messages: state.currentConversationId === id ? [] : state.messages
        }))
    }),
    {
      name: 'chief-of-staff-storage',
      partialize: (state) => ({
        conversations: state.conversations,
        documentIds: state.documentIds
      })
    }
  )
)
