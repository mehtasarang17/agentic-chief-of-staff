'use client'

import { motion } from 'framer-motion'
import { useConversationStore } from '@/lib/store'
import { agentColors, agentIcons } from '@/lib/utils'

interface AgentPanelProps {
  onClose: () => void
}

export default function AgentPanel({ onClose }: AgentPanelProps) {
  const { agents } = useConversationStore()

  return (
    <div className="h-full flex flex-col glass-dark w-80">
      {/* Header */}
      <div className="p-4 border-b border-dark-700/50">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500/20 to-accent-500/20 flex items-center justify-center">
              <svg className="w-5 h-5 text-primary-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <h2 className="font-semibold text-white">AI Agents</h2>
              <p className="text-xs text-dark-400">{agents.length} agents available</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 hover:bg-dark-700/50 rounded-lg transition-colors text-dark-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Agent List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {agents.map((agent, index) => (
          <motion.div
            key={agent.id}
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.05 }}
          >
            <AgentCard agent={agent} />
          </motion.div>
        ))}
      </div>

      {/* Footer Stats */}
      <div className="p-4 border-t border-dark-700/50">
        <div className="glass rounded-xl p-3">
          <h3 className="text-xs font-medium text-dark-400 mb-2">Agent Coordination</h3>
          <div className="flex items-center gap-2">
            <div className="flex-1 h-2 bg-dark-700 rounded-full overflow-hidden">
              <motion.div
                className="h-full bg-gradient-to-r from-primary-500 to-accent-500"
                initial={{ width: 0 }}
                animate={{ width: '100%' }}
                transition={{ duration: 1, ease: 'easeOut' }}
              />
            </div>
            <span className="text-xs text-dark-400">Ready</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function AgentCard({ agent }: { agent: any }) {
  const color = agentColors[agent.name] || agentColors.orchestrator
  const icon = agentIcons[agent.name] || agentIcons.orchestrator

  const statusColors = {
    idle: 'bg-dark-600 text-dark-400',
    thinking: 'bg-yellow-500/20 text-yellow-400',
    working: 'bg-green-500/20 text-green-400',
  }

  const statusLabels = {
    idle: 'Idle',
    thinking: 'Thinking',
    working: 'Working',
  }

  return (
    <div className="glass rounded-xl p-4 hover:bg-white/5 transition-all group">
      <div className="flex items-start gap-3">
        {/* Agent Icon */}
        <div className="relative">
          {agent.status !== 'idle' && (
            <div className={`absolute inset-0 bg-gradient-to-br ${color} rounded-lg opacity-50 blur animate-pulse`} />
          )}
          <div
            className={`relative w-10 h-10 rounded-lg bg-gradient-to-br ${color} flex items-center justify-center ${
              agent.status !== 'idle' ? 'shadow-glow' : ''
            }`}
          >
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
            </svg>
          </div>
        </div>

        {/* Agent Info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <h3 className="font-medium text-white truncate">{agent.displayName}</h3>
            <span className={`px-2 py-0.5 rounded-full text-xs ${statusColors[agent.status as keyof typeof statusColors]}`}>
              {statusLabels[agent.status as keyof typeof statusLabels]}
            </span>
          </div>
          <p className="text-xs text-dark-400 mt-0.5 line-clamp-2">{agent.description}</p>

          {/* Capabilities */}
          <div className="flex flex-wrap gap-1 mt-2">
            {agent.capabilities.slice(0, 3).map((cap: string, i: number) => (
              <span key={i} className="px-2 py-0.5 bg-dark-700/50 rounded text-xs text-dark-400">
                {cap}
              </span>
            ))}
            {agent.capabilities.length > 3 && (
              <span className="px-2 py-0.5 text-xs text-dark-500">
                +{agent.capabilities.length - 3}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Active indicator */}
      {agent.status !== 'idle' && (
        <motion.div
          className="mt-3 pt-3 border-t border-dark-700/50"
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
        >
          <div className="flex items-center gap-2 text-xs text-dark-400">
            <div className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse" />
            Processing request...
          </div>
        </motion.div>
      )}
    </div>
  )
}
