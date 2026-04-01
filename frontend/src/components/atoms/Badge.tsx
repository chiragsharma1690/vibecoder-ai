import React from 'react';
import { cn } from '../../utils/cn';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger';
  className?: string;
}

export const Badge = ({ children, variant = 'default', className }: BadgeProps) => {
  const variants = {
    default: 'bg-zinc-800 text-zinc-300 border-zinc-700',
    success: 'bg-emerald-950/50 text-emerald-400 border-emerald-900/50',
    warning: 'bg-amber-950/50 text-amber-400 border-amber-900/50',
    danger: 'bg-red-950/50 text-red-400 border-red-900/50',
  };

  return (
    <span className={cn(
      "px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider border",
      variants[variant],
      className
    )}>
      {children}
    </span>
  );
};