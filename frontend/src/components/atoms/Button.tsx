import React, { ButtonHTMLAttributes, forwardRef } from 'react';
import { Spinner } from './Spinner';
import { cn } from '../../utils/cn';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  icon?: React.ReactNode;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ children, variant = 'primary', size = 'md', isLoading, icon, className, disabled, ...props }, ref) => {
    
    const baseStyles = 'inline-flex items-center justify-center gap-2 font-medium transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-zinc-950 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg';
    
    const variants = {
      primary: 'bg-zinc-100 text-zinc-900 hover:bg-white focus:ring-zinc-100',
      secondary: 'bg-zinc-800 text-zinc-200 hover:bg-zinc-700 border border-zinc-700 focus:ring-zinc-700',
      ghost: 'bg-transparent text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800/50 focus:ring-zinc-700',
      danger: 'bg-red-900/80 text-red-100 hover:bg-red-800 border border-red-800 focus:ring-red-700',
    };

    const sizes = {
      sm: 'text-xs px-3 py-1.5',
      md: 'text-sm px-4 py-2',
      lg: 'text-base px-5 py-2.5',
    };

    return (
      <button 
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? <Spinner size={size === 'sm' ? 14 : 16} className={variant === 'primary' ? 'text-zinc-600' : ''} /> : icon}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';