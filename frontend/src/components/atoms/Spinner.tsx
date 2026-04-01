import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

interface SpinnerProps {
  size?: number;
  className?: string;
}

export const Spinner = ({ size = 16, className }: SpinnerProps) => {
  return (
    <Loader2 
      size={size} 
      className={cn("animate-spin text-gray-400 dark:text-zinc-400 transition-colors", className)} 
    />
  );
};