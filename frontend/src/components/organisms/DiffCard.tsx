import { useState, useEffect } from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued';
import { FileCode, ChevronDown, ChevronUp } from 'lucide-react';
import { FileDiff } from '../../types';
import { Badge } from '../atoms/Badge';

export const DiffCard = ({ diffs }: { diffs: FileDiff[] }) => {
  const [expandedFiles, setExpandedFiles] = useState<Record<string, boolean>>(
    diffs.reduce((acc, curr, idx) => ({ ...acc, [curr.file]: idx === 0 }), {})
  );

  // Dynamically track the global dark mode state
  const [isDark, setIsDark] = useState(() => {
    if (typeof window !== 'undefined') {
      return document.documentElement.classList.contains('dark');
    }
    return true;
  });

  useEffect(() => {
    const observer = new MutationObserver(() => {
      setIsDark(document.documentElement.classList.contains('dark'));
    });
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['class'] });
    return () => observer.disconnect();
  }, []);

  const toggleFile = (filename: string) => {
    setExpandedFiles(prev => ({ ...prev, [filename]: !prev[filename] }));
  };

  const customStyles = {
    variables: {
      light: {
        diffViewerBackground: '#ffffff',
        diffViewerColor: '#1f2937',
        addedBackground: '#ecfdf5',
        addedColor: '#047857',
        removedBackground: '#fef2f2',
        removedColor: '#b91c1c',
        wordAddedBackground: '#a7f3d0',
        wordRemovedBackground: '#fecaca',
        lineNumberColor: '#9ca3af',
        emptyLineBackground: '#f9fafb',
      },
      dark: {
        diffViewerBackground: '#09090b',
        diffViewerColor: '#d4d4d8',
        addedBackground: '#064e3b',
        addedColor: '#34d399',
        removedBackground: '#7f1d1d',
        removedColor: '#f87171',
        wordAddedBackground: '#047857',
        wordRemovedBackground: '#991b1b',
        lineNumberColor: '#52525b',
        emptyLineBackground: '#18181b',
      }
    }
  };

  if (!diffs || diffs.length === 0) return null;

  return (
    <div className="mt-4 space-y-4 w-full max-w-4xl animate-fade-in">
      {diffs.map((diff, index) => {
        const isExpanded = expandedFiles[diff.file];
        const isNewFile = !diff.old_content && diff.new_content;

        return (
          <div key={index} className="bg-white dark:bg-zinc-950 border border-gray-200 dark:border-zinc-800 rounded-xl overflow-hidden shadow-lg transition-colors duration-300">
            <button 
              onClick={() => toggleFile(diff.file)}
              className="w-full flex items-center justify-between p-3 bg-gray-50 dark:bg-zinc-900/50 hover:bg-gray-100 dark:hover:bg-zinc-800/50 transition-colors border-b border-gray-200 dark:border-zinc-800"
            >
              <div className="flex items-center gap-3">
                <FileCode size={18} className={isNewFile ? "text-emerald-600 dark:text-emerald-400" : "text-indigo-600 dark:text-indigo-400"} />
                <span className="font-mono text-sm text-gray-800 dark:text-zinc-300 transition-colors">{diff.file}</span>
                {isNewFile && <Badge variant="success">New File</Badge>}
              </div>
              {isExpanded ? <ChevronUp size={18} className="text-gray-500 dark:text-zinc-500" /> : <ChevronDown size={18} className="text-gray-500 dark:text-zinc-500" />}
            </button>

            {isExpanded && (
              <div className="text-xs overflow-x-auto custom-scrollbar">
                <ReactDiffViewer
                  oldValue={diff.old_content}
                  newValue={diff.new_content}
                  splitView={true}
                  compareMethod={DiffMethod.WORDS}
                  useDarkTheme={isDark}
                  styles={customStyles}
                  leftTitle={isNewFile ? "Doesn't Exist" : "Original Code"}
                  rightTitle="AI Generated Code"
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};