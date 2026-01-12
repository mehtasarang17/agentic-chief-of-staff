'use client'

import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { useConversationStore, Conversation } from '@/lib/store'
import { api } from '@/lib/api'
import { formatDate, truncate } from '@/lib/utils'

interface SidebarProps {
  onClose: () => void
}

export default function Sidebar({ onClose }: SidebarProps) {
  const {
    conversations,
    currentConversationId,
    setConversations,
    setCurrentConversation,
    setMessages,
    clearMessages,
    deleteConversation,
  } = useConversationStore()

  const [isLoading, setIsLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    loadConversations()
  }, [])

  const loadConversations = async () => {
    try {
      setIsLoading(true)
      const response = await api.getConversations()
      setConversations(
        response.conversations.map((c) => ({
          id: c.id,
          title: c.title,
          lastMessage: c.last_message,
          updatedAt: new Date(c.updated_at),
          messageCount: c.message_count,
        }))
      )
    } catch (error) {
      console.error('Failed to load conversations:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = () => {
    clearMessages()
  }

  const handleSelectConversation = async (id: string) => {
    try {
      setCurrentConversation(id)
      const response = await api.getConversation(id)
      setMessages(
        response.messages.map((m: any) => ({
          id: m.id,
          role: m.role,
          content: m.content,
          agentName: m.agent_name,
          thoughts: m.thoughts,
          toolCalls: m.tool_calls,
          timestamp: new Date(m.created_at),
        }))
      )
    } catch (error) {
      console.error('Failed to load conversation:', error)
    }
  }

  const handleDeleteConversation = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.deleteConversation(id)
      deleteConversation(id)
    } catch (error) {
      console.error('Failed to delete conversation:', error)
    }
  }

  const filteredConversations = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  )

  return (
    <div className="h-full flex flex-col glass-dark">
      {/* Header */}
      <div className="p-4 border-b border-dark-700/50">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-accent-500 flex items-center justify-center">
              <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="font-semibold text-white">Conversations</span>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-dark-700/50 rounded-lg transition-colors text-dark-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
            </svg>
          </button>
        </div>

        {/* New Chat Button */}
        <button
          onClick={handleNewChat}
          className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-gradient-to-r from-primary-500 to-accent-500 hover:from-primary-600 hover:to-accent-600 text-white rounded-xl font-medium transition-all shadow-glow hover:shadow-glow-lg"
        >
          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New Conversation
        </button>

        {/* Search */}
        <div className="mt-4 relative">
          <svg
            className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-dark-400"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search conversations..."
            className="w-full pl-10 pr-4 py-2.5 bg-dark-800/50 border border-dark-700/50 rounded-lg text-sm text-white placeholder-dark-400 focus:outline-none focus:ring-2 focus:ring-primary-500/50 focus:border-primary-500/50 transition-all"
          />
        </div>
      </div>

      {/* Conversation List */}
      <div className="flex-1 overflow-y-auto p-2">
        {isLoading ? (
          <div className="flex items-center justify-center py-8">
            <div className="w-6 h-6 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="text-center py-8 text-dark-400">
            <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
            </svg>
            <p className="text-sm">No conversations yet</p>
            <p className="text-xs mt-1 text-dark-500">Start a new chat to begin</p>
          </div>
        ) : (
          <div className="space-y-1">
            {filteredConversations.map((conversation, index) => (
              <motion.div
                key={conversation.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ delay: index * 0.05 }}
              >
                <button
                  onClick={() => handleSelectConversation(conversation.id)}
                  className={`w-full group flex items-start gap-3 p-3 rounded-xl transition-all ${
                    currentConversationId === conversation.id
                      ? 'bg-primary-500/20 border border-primary-500/30'
                      : 'hover:bg-dark-700/50 border border-transparent'
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                      currentConversationId === conversation.id
                        ? 'bg-primary-500/30 text-primary-400'
                        : 'bg-dark-700/50 text-dark-400'
                    }`}
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                    </svg>
                  </div>
                  <div className="flex-1 min-w-0 text-left">
                    <p
                      className={`text-sm font-medium truncate ${
                        currentConversationId === conversation.id
                          ? 'text-white'
                          : 'text-dark-200'
                      }`}
                    >
                      {conversation.title}
                    </p>
                    {conversation.lastMessage && (
                      <p className="text-xs text-dark-400 truncate mt-0.5">
                        {truncate(conversation.lastMessage, 40)}
                      </p>
                    )}
                    <p className="text-xs text-dark-500 mt-1">
                      {formatDate(conversation.updatedAt)}
                    </p>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conversation.id, e)}
                    className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-500/20 rounded transition-all text-dark-400 hover:text-red-400"
                  >
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                    </svg>
                  </button>
                </button>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-dark-700/50">
        <div className="flex items-center gap-2 text-dark-400">
          <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse" />
          <span className="text-xs">Connected to AI Backend</span>
        </div>
      </div>
    </div>
  )
}
