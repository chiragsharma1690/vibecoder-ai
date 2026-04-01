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
        {label && <label className="text-xs font-medium text-zinc-400">{label}</label>}
        <textarea
          ref={ref}
          className={cn(
            "w-full bg-zinc-900/50 border rounded-lg px-4 py-3 text-sm text-zinc-100 placeholder:text-zinc-600 transition-all duration-200 focus:outline-none focus:ring-2 resize-none",
            error 
              ? "border-red-900 focus:border-red-500 focus:ring-red-500/20" 
              : "border-zinc-800 focus:border-zinc-600 focus:ring-zinc-600/20",
            className
          )}
          {...props}
        />
        {error && <span className="text-[11px] text-red-400">{error}</span>}
      </div>
    );
  }
);
TextArea.displayName = 'TextArea';