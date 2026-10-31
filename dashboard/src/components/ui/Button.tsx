'use client'

import React, { forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'sm' | 'md' | 'lg'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled}
        className={cn(
          'inline-flex items-center justify-center font-sans font-medium transition-colors select-none focus:outline-none focus:ring-1 focus:ring-ink disabled:opacity-50 disabled:pointer-events-none rounded-none',
          size === 'sm' && 'px-2.5 py-1 text-xs',
          size === 'md' && 'px-4 py-2 text-xs',
          size === 'lg' && 'px-5 py-2.5 text-sm',
          variant === 'primary' && 'bg-vermilion text-white hover:bg-ink hover:text-white',
          variant === 'secondary' && 'bg-paper-high text-ink border border-border hover:bg-paper-highest',
          variant === 'danger' && 'bg-vermilion/10 text-vermilion border border-vermilion/30 hover:bg-vermilion hover:text-white',
          variant === 'ghost' && 'text-ink-muted hover:text-ink hover:bg-paper-high',
          className
        )}
        {...props}
      >
        {children}
      </button>
    )
  }
)
Button.displayName = 'Button'
