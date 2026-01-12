'use client'

import { motion } from 'framer-motion'
import { useConversationStore } from '@/lib/store'
import ChatInput from '@/components/ChatInput'

const suggestions = [
  {
    icon: '📅',
    title: 'Schedule a meeting',
    description: 'with the marketing team for next week',
    color: 'from-blue-500 to-cyan-500',
  },
  {
    icon: '✉️',
    title: 'Draft an email',
    description: 'to follow up on the Q4 proposal',
    color: 'from-green-500 to-emerald-500',
  },
  {
    icon: '🔍',
    title: 'Research competitors',
    description: 'in the AI assistant space',
    color: 'from-purple-500 to-violet-500',
  },
  {
    icon: '📊',
    title: 'Generate a report',
    description: 'on this month\'s KPI performance',
    color: 'from-pink-500 to-rose-500',
  },
]

const features = [
  { icon: '🤖', title: 'Multi-Agent AI', description: 'Specialized agents for every task' },
  { icon: '🧠', title: 'Contextual Memory', description: 'Remembers your preferences' },
  { icon: '📄', title: 'Document RAG', description: 'Search your uploaded files' },
  { icon: '⚡', title: 'Real-time', description: 'Instant responses & updates' },
]

export default function WelcomeScreen() {
  return (
    <div className="h-full flex flex-col">
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-6 py-12">
          {/* Hero Section */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="text-center mb-12"
          >
            {/* Animated Logo */}
            <motion.div
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              transition={{ type: 'spring', damping: 10, stiffness: 100, delay: 0.2 }}
              className="w-24 h-24 mx-auto mb-6 relative"
            >
              <div className="absolute inset-0 bg-gradient-to-br from-primary-500 to-accent-500 rounded-2xl rotate-6 opacity-50 blur-xl animate-pulse-slow" />
              <div className="relative w-full h-full bg-gradient-to-br from-primary-500 to-accent-500 rounded-2xl flex items-center justify-center shadow-glow">
                <svg className="w-12 h-12 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
              </div>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-4xl font-bold text-white mb-3"
            >
              Welcome to{' '}
              <span className="bg-gradient-to-r from-primary-400 to-accent-400 bg-clip-text text-transparent">
                Chief of Staff
              </span>
            </motion.h1>

            <motion.p
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="text-lg text-dark-300 max-w-xl mx-auto"
            >
              Your AI-powered executive assistant with multi-agent orchestration.
              I can help you manage calendars, emails, research, tasks, and analytics.
            </motion.p>
          </motion.div>

          {/* Features Grid */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.5 }}
            className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-12"
          >
            {features.map((feature, index) => (
              <motion.div
                key={feature.title}
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ delay: 0.6 + index * 0.1 }}
                className="glass rounded-xl p-4 text-center hover:bg-white/10 transition-colors"
              >
                <div className="text-3xl mb-2">{feature.icon}</div>
                <h3 className="text-sm font-medium text-white mb-1">{feature.title}</h3>
                <p className="text-xs text-dark-400">{feature.description}</p>
              </motion.div>
            ))}
          </motion.div>

          {/* Suggestions */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
            className="mb-8"
          >
            <h2 className="text-sm font-medium text-dark-400 mb-4 text-center">
              Try asking me to...
            </h2>
            <div className="grid md:grid-cols-2 gap-3">
              {suggestions.map((suggestion, index) => (
                <SuggestionCard key={index} suggestion={suggestion} index={index} />
              ))}
            </div>
          </motion.div>
        </div>
      </div>

      {/* Chat Input */}
      <div className="border-t border-dark-700/50 p-4">
        <ChatInput />
      </div>
    </div>
  )
}

function SuggestionCard({
  suggestion,
  index,
}: {
  suggestion: (typeof suggestions)[0]
  index: number
}) {
  const { addMessage, setLoading } = useConversationStore()

  const handleClick = () => {
    const message = `${suggestion.title} ${suggestion.description}`
    addMessage({
      id: Math.random().toString(36).substring(7),
      role: 'user',
      content: message,
      timestamp: new Date(),
    })
    // The ChatInput component will handle sending
  }

  return (
    <motion.button
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ delay: 0.9 + index * 0.1 }}
      onClick={handleClick}
      className="group flex items-start gap-4 p-4 glass rounded-xl text-left hover:bg-white/10 transition-all border border-transparent hover:border-white/10"
    >
      <div
        className={`w-10 h-10 rounded-lg bg-gradient-to-br ${suggestion.color} flex items-center justify-center flex-shrink-0 shadow-lg group-hover:scale-110 transition-transform`}
      >
        <span className="text-lg">{suggestion.icon}</span>
      </div>
      <div>
        <h3 className="font-medium text-white group-hover:text-primary-400 transition-colors">
          {suggestion.title}
        </h3>
        <p className="text-sm text-dark-400">{suggestion.description}</p>
      </div>
    </motion.button>
  )
}
