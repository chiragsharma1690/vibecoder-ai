import { TextareaHTMLAttributes, forwardRef } from 'react';
import { cn } from '../../utils/cn';

interface TextAreaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
}

export const TextArea = forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, error, className, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1.5 w-full">
        {label && <label className="text-xs font-medium text-gray-600 dark:text-zinc-400 transition-colors">{label}</label>}
        <textarea
          ref={ref}
          className={cn(
            "w-full bg-white dark:bg-zinc-900/50 border rounded-lg px-4 py-3 text-sm text-gray-900 dark:text-zinc-100 placeholder:text-gray-400 dark:placeholder:text-zinc-600 transition-all duration-200 focus:outline-none focus:ring-2 resize-none",
            error 
              ? "border-red-500 dark:border-red-900 focus:border-red-500 focus:ring-red-500/20" 
              : "border-gray-300 dark:border-zinc-800 focus:border-indigo-500 dark:focus:border-zinc-600 focus:ring-indigo-500/20 dark:focus:ring-zinc-600/20",
            className
          )}
          {...props}
        />
        {error && <span className="text-[11px] text-red-500 dark:text-red-400 transition-colors">{error}</span>}
      </div>
    );
  }
);
TextArea.displayName = 'TextArea';