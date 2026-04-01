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
    
    const baseStyles = 'inline-flex items-center justify-center gap-2 font-medium transition-all duration-200 ease-out focus:outline-none focus:ring-2 focus:ring-offset-2 dark:focus:ring-offset-zinc-950 disabled:opacity-50 disabled:cursor-not-allowed rounded-lg';
    
    const variants = {
      primary: 'bg-indigo-600 text-white hover:bg-indigo-700 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-white focus:ring-indigo-600 dark:focus:ring-zinc-100',
      secondary: 'bg-white text-gray-700 hover:bg-gray-50 border border-gray-300 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700 dark:border-zinc-700 focus:ring-gray-200 dark:focus:ring-zinc-700',
      ghost: 'bg-transparent text-gray-500 hover:text-gray-900 hover:bg-gray-100 dark:text-zinc-400 dark:hover:text-zinc-200 dark:hover:bg-zinc-800/50 focus:ring-gray-200 dark:focus:ring-zinc-700',
      danger: 'bg-red-500 text-white hover:bg-red-600 dark:bg-red-900/80 dark:text-red-100 dark:hover:bg-red-800 border border-red-600 dark:border-red-800 focus:ring-red-500 dark:focus:ring-red-700',
    };

    const sizes = { sm: 'text-xs px-3 py-1.5', md: 'text-sm px-4 py-2', lg: 'text-base px-5 py-2.5' };

    return (
      <button ref={ref} className={cn(baseStyles, variants[variant], sizes[size], className)} disabled={disabled || isLoading} {...props}>
        {isLoading ? <Spinner size={size === 'sm' ? 14 : 16} className={variant === 'primary' ? 'text-white dark:text-zinc-600' : ''} /> : icon}
        {children}
      </button>
    );
  }
);
Button.displayName = 'Button';