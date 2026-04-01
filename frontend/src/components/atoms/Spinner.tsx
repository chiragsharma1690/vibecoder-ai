import { Loader2 } from 'lucide-react';
import { cn } from '../../utils/cn';

interface SpinnerProps {
  size?: number;
  className?: string;
}

export const Spinner = ({ size = 16, className }: SpinnerProps) => {
  return <Loader2 size={size} className={cn("animate-spin text-zinc-400", className)} />;
};