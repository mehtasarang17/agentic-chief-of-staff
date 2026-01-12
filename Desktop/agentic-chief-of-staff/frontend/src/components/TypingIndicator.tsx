'use client'

import { motion } from 'framer-motion'
import { agentColors, agentIcons } from '@/lib/utils'

interface TypingIndicatorProps {
  agentName: string
}

export default function TypingIndicator({ agentName }: TypingIndicatorProps) {
  const normalizedName = agentName.toLowerCase().replace(' ', '_')
  const color = agentColors[normalizedName] || agentColors.orchestrator
  const icon = agentIcons[normalizedName] || agentIcons.orchestrator

  return (
    <div className="flex gap-4 mb-6">
      {/* Avatar with pulse effect */}
      <div className="flex-shrink-0">
        <div className="relative">
          <div className={`absolute inset-0 bg-gradient-to-br ${color} rounded-xl opacity-50 blur animate-pulse`} />
          <div className={`relative w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center shadow-glow`}>
            <svg className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={icon} />
            </svg>
          </div>
        </div>
      </div>

      {/* Typing Content */}
      <div className="flex-1">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-medium text-white">{formatAgentName(agentName)}</span>
          <span className="text-xs text-primary-400 animate-pulse">thinking...</span>
        </div>

        <div className="glass rounded-2xl rounded-tl-md px-4 py-3 inline-block">
          <div className="flex items-center gap-2">
            {/* Animated dots */}
            <div className="flex gap-1">
              {[0, 1, 2].map((i) => (
                <motion.div
                  key={i}
                  className="w-2 h-2 bg-primary-500 rounded-full"
                  animate={{
                    scale: [1, 1.2, 1],
                    opacity: [0.5, 1, 0.5],
                  }}
                  transition={{
                    duration: 1,
                    repeat: Infinity,
                    delay: i * 0.2,
                  }}
                />
              ))}
            </div>

            {/* Status text */}
            <motion.span
              className="text-sm text-dark-400"
              animate={{ opacity: [0.5, 1, 0.5] }}
              transition={{ duration: 2, repeat: Infinity }}
            >
              Analyzing your request...
            </motion.span>
          </div>
        </div>
      </div>
    </div>
  )
}

function formatAgentName(name: string): string {
  const names: Record<string, string> = {
    orchestrator: 'Chief of Staff',
    'chief of staff': 'Chief of Staff',
    calendar: 'Calendar Manager',
    email: 'Email Manager',
    research: 'Research Analyst',
    task: 'Task Manager',
    analytics: 'Analytics Expert',
    pdf: 'PDF Export',
  }
  return names[name.toLowerCase()] || name
}
