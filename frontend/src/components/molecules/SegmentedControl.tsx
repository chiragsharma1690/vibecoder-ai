import { cn } from '../../utils/cn';

interface Option {
  label: string;
  value: string;
}

interface SegmentedControlProps {
  options: Option[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

export const SegmentedControl = ({ options, value, onChange, disabled }: SegmentedControlProps) => {
  return (
    <div className={cn("flex p-1 space-x-1 bg-zinc-900/80 border border-zinc-800 rounded-lg w-fit", disabled && "opacity-50 pointer-events-none")}>
      {options.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            "px-4 py-1.5 text-xs font-medium rounded-md transition-all duration-200",
            value === opt.value
              ? "bg-zinc-800 text-zinc-100 shadow-sm border border-zinc-700/50"
              : "text-zinc-500 hover:text-zinc-300 hover:bg-zinc-800/50 border border-transparent"
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
};