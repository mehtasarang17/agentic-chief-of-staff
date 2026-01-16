'use client'

import { useState, useRef, KeyboardEvent } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useConversationStore } from '@/lib/store'
import { api } from '@/lib/api'
import { generateId } from '@/lib/utils'

export default function ChatInput() {
  const [message, setMessage] = useState('')
  const [isUploading, setIsUploading] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const {
    currentConversationId,
    isLoading,
    addMessage,
    setLoading,
    setActiveAgent,
    updateAgentStatus,
    setCurrentConversation,
    addConversation,
    documentIds,
    addDocumentId,
  } = useConversationStore()

  const handleSubmit = async () => {
    if (!message.trim() || isLoading) return

    const userMessage = message.trim()
    setMessage('')

    // Add user message immediately
    const userMessageId = generateId()
    addMessage({
      id: userMessageId,
      role: 'user',
      content: userMessage,
      timestamp: new Date(),
    })

    // Start loading state
    setLoading(true)
    setActiveAgent('orchestrator')
    updateAgentStatus('orchestrator', 'thinking')

    try {
      const response = await api.sendMessage({
        message: userMessage,
        conversation_id: currentConversationId || undefined,
        use_rag: true,
        context: documentIds.length ? { document_ids: documentIds } : undefined,
      })

      // Update conversation if new
      if (!currentConversationId) {
        setCurrentConversation(response.conversation_id)
        addConversation({
          id: response.conversation_id,
          title: userMessage.slice(0, 50) + (userMessage.length > 50 ? '...' : ''),
          lastMessage: response.response.slice(0, 100),
          updatedAt: new Date(),
          messageCount: 2,
        })
      }

      // Add assistant response
      addMessage({
        id: response.message_id,
        role: 'assistant',
        content: response.response,
        agentName: response.agent,
        thoughts: response.thoughts,
        toolCalls: response.tool_calls,
        sources: response.sources,
        agentSteps: response.all_results,
        timestamp: new Date(),
      })
    } catch (error) {
      console.error('Failed to send message:', error)
      addMessage({
        id: generateId(),
        role: 'assistant',
        content: 'I apologize, but I encountered an error processing your request. Please try again.',
        agentName: 'orchestrator',
        timestamp: new Date(),
      })
    } finally {
      setLoading(false)
      setActiveAgent(null)
      updateAgentStatus('orchestrator', 'idle')
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit()
    }
  }

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    setIsUploading(true)
    try {
      const upload = await api.uploadDocument(file)
      if (upload?.id) {
        addDocumentId(upload.id)
      }
      // Show success message
      addMessage({
        id: generateId(),
        role: 'assistant',
        content: `Document "${file.name}" uploaded successfully! I can now search through this document when answering your questions.`,
        agentName: 'orchestrator',
        timestamp: new Date(),
      })
    } catch (error) {
      console.error('Failed to upload document:', error)
      addMessage({
        id: generateId(),
        role: 'assistant',
        content: `Failed to upload "${file.name}". Please try again.`,
        agentName: 'orchestrator',
        timestamp: new Date(),
      })
    } finally {
      setIsUploading(false)
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }
    }
  }

  // Auto-resize textarea
  const handleTextareaChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setMessage(e.target.value)
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px'
    }
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="relative">
        {/* Main Input Container */}
        <div className="glass rounded-2xl overflow-hidden border border-dark-700/50 focus-within:border-primary-500/50 focus-within:ring-2 focus-within:ring-primary-500/20 transition-all">
          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={message}
            onChange={handleTextareaChange}
            onKeyDown={handleKeyDown}
            placeholder="Message Chief of Staff..."
            disabled={isLoading}
            rows={1}
            className="w-full px-4 py-4 pr-32 bg-transparent text-white placeholder-dark-400 resize-none focus:outline-none disabled:opacity-50"
            style={{ minHeight: '56px', maxHeight: '200px' }}
          />

          {/* Actions */}
          <div className="absolute right-2 bottom-2 flex items-center gap-1">
            {/* Upload Button */}
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.txt,.md,.docx,.xlsx,.csv"
              onChange={handleFileUpload}
              className="hidden"
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={isLoading || isUploading}
              className="p-2 text-dark-400 hover:text-white hover:bg-dark-700/50 rounded-lg transition-all disabled:opacity-50"
              title="Upload document"
            >
              {isUploading ? (
                <div className="w-5 h-5 border-2 border-primary-500 border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              )}
            </button>

            {/* Microphone Button (placeholder) */}
            <button
              disabled={isLoading}
              className="p-2 text-dark-400 hover:text-white hover:bg-dark-700/50 rounded-lg transition-all disabled:opacity-50"
              title="Voice input (coming soon)"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
              </svg>
            </button>

            {/* Send Button */}
            <button
              onClick={handleSubmit}
              disabled={!message.trim() || isLoading}
              className={`p-2 rounded-lg transition-all ${
                message.trim() && !isLoading
                  ? 'bg-gradient-to-r from-primary-500 to-accent-500 text-white shadow-glow hover:shadow-glow-lg'
                  : 'bg-dark-700/50 text-dark-500'
              }`}
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </div>
        </div>

        {/* Hints */}
        <div className="flex items-center justify-between mt-2 px-1">
          <p className="text-xs text-dark-500">
            Press <kbd className="px-1.5 py-0.5 bg-dark-700/50 rounded text-dark-400">Enter</kbd> to send,{' '}
            <kbd className="px-1.5 py-0.5 bg-dark-700/50 rounded text-dark-400">Shift+Enter</kbd> for new line
          </p>
          <p className="text-xs text-dark-500">
            Powered by GPT-4o-mini
          </p>
        </div>
      </div>
    </div>
  )
}
