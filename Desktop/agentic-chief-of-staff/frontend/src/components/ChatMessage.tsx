'use client'

import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import ReactMarkdown from 'react-markdown'
import { Message } from '@/lib/store'
import { agentColors, agentIcons, formatDate } from '@/lib/utils'

interface ChatMessageProps {
  message: Message
  isLast: boolean
}

export default function ChatMessage({ message, isLast }: ChatMessageProps) {
  const [showDetails, setShowDetails] = useState(false)
  const isUser = message.role === 'user'
  const agentName = message.agentName || 'orchestrator'

  return (
    <div className={`flex gap-4 mb-6 ${isUser ? 'flex-row-reverse' : ''}`}>
      {/* Avatar */}
      <div className="flex-shrink-0">
        {isUser ? (
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-dark-600 to-dark-700 flex items-center justify-center">
            <svg className="w-5 h-5 text-dark-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
            </svg>
          </div>
        ) : (
          <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${agentColors[agentName] || agentColors.orchestrator} flex items-center justify-center shadow-glow`}>
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={agentIcons[agentName] || agentIcons.orchestrator} />
            </svg>
          </div>
        )}
      </div>

      {/* Message Content */}
      <div className={`flex-1 min-w-0 ${isUser ? 'text-right' : ''}`}>
        {/* Header */}
        <div className={`flex items-center gap-2 mb-1 ${isUser ? 'justify-end' : ''}`}>
          <span className="text-sm font-medium text-white">
            {isUser ? 'You' : message.agentName ? formatAgentName(message.agentName) : 'Chief of Staff'}
          </span>
          <span className="text-xs text-dark-500">
            {formatDate(message.timestamp)}
          </span>
        </div>

        {/* Message Bubble */}
        <div
          className={`inline-block max-w-full ${
            isUser
              ? 'bg-gradient-to-br from-primary-500 to-primary-600 text-white rounded-2xl rounded-tr-md'
              : 'glass rounded-2xl rounded-tl-md'
          } px-4 py-3`}
        >
          <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : 'prose-dark'}`}>
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                ul: ({ children }) => <ul className="list-disc list-inside mb-2">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal list-inside mb-2">{children}</ol>,
                li: ({ children }) => <li className="mb-1">{children}</li>,
                code: ({ children, className }) => {
                  const isInline = !className
                  if (isInline) {
                    return (
                      <code className="px-1.5 py-0.5 bg-dark-800/50 rounded text-primary-400 text-xs font-mono">
                        {children}
                      </code>
                    )
                  }
                  return (
                    <code className="block p-3 bg-dark-900 rounded-lg text-xs font-mono overflow-x-auto">
                      {children}
                    </code>
                  )
                },
                pre: ({ children }) => <pre className="mb-2">{children}</pre>,
                strong: ({ children }) => <strong className="font-semibold text-white">{children}</strong>,
                em: ({ children }) => <em className="italic">{children}</em>,
                a: ({ href, children }) => (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:underline">
                    {children}
                  </a>
                ),
              }}
            >
              {message.content}
            </ReactMarkdown>
          </div>
        </div>

        {/* Agent Details */}
        {!isUser && (message.thoughts?.length || message.toolCalls?.length || message.sources?.length) && (
          <div className="mt-2">
            <button
              onClick={() => setShowDetails(!showDetails)}
              className="flex items-center gap-1 text-xs text-dark-400 hover:text-primary-400 transition-colors"
            >
              <svg
                className={`w-3 h-3 transition-transform ${showDetails ? 'rotate-90' : ''}`}
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
              View agent details
            </button>

            <AnimatePresence>
              {showDetails && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="mt-2 overflow-hidden"
                >
                  <div className="glass rounded-lg p-3 space-y-3">
                    {/* Agent Thoughts */}
                    {message.thoughts && message.thoughts.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-dark-300 mb-1 flex items-center gap-1">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                          </svg>
                          Agent Reasoning
                        </h4>
                        <ul className="text-xs text-dark-400 space-y-1">
                          {message.thoughts.map((thought, i) => (
                            <li key={i} className="flex items-start gap-1">
                              <span className="text-primary-400">•</span>
                              {thought}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {/* Tool Calls */}
                    {message.toolCalls && message.toolCalls.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-dark-300 mb-1 flex items-center gap-1">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                          </svg>
                          Tools Used
                        </h4>
                        <div className="flex flex-wrap gap-1">
                          {message.toolCalls.map((tool, i) => (
                            <span
                              key={i}
                              className="px-2 py-0.5 bg-dark-700/50 rounded text-xs text-dark-300"
                            >
                              {tool.tool || tool.action || 'Unknown tool'}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Sources */}
                    {message.sources && message.sources.length > 0 && (
                      <div>
                        <h4 className="text-xs font-medium text-dark-300 mb-1 flex items-center gap-1">
                          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          Sources
                        </h4>
                        <div className="space-y-1">
                          {message.sources.map((source, i) => (
                            <div
                              key={i}
                              className="flex items-center gap-2 text-xs text-dark-400"
                            >
                              <span className="w-4 h-4 rounded bg-dark-700/50 flex items-center justify-center text-[10px]">
                                {i + 1}
                              </span>
                              {source.filename || source.document_id || 'Document'}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  )
}

function formatAgentName(name: string): string {
  const names: Record<string, string> = {
    orchestrator: 'Chief of Staff',
    calendar: 'Calendar Manager',
    email: 'Email Manager',
    research: 'Research Analyst',
    task: 'Task Manager',
    analytics: 'Analytics Expert',
    pdf: 'PDF Export',
    synthesizer: 'Chief of Staff',
  }
  return names[name] || name
}
