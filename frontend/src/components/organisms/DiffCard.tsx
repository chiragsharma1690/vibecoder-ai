import { useState } from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued';
import { FileCode, ChevronDown, ChevronUp } from 'lucide-react';
import { FileDiff } from '../../types';
import { Badge } from '../atoms/Badge';

export const DiffCard = ({ diffs }: { diffs: FileDiff[] }) => {
  const [expandedFiles, setExpandedFiles] = useState<Record<string, boolean>>(
    diffs.reduce((acc, curr, idx) => ({ ...acc, [curr.file]: idx === 0 }), {})
  );

  const toggleFile = (filename: string) => {
    setExpandedFiles(prev => ({ ...prev, [filename]: !prev[filename] }));
  };

  const customStyles = {
    variables: {
      dark: {
        diffViewerBackground: '#09090b', // zinc-950
        diffViewerColor: '#d4d4d8', // zinc-300
        addedBackground: '#064e3b', // emerald-900
        addedColor: '#34d399', // emerald-400
        removedBackground: '#7f1d1d', // red-900
        removedColor: '#f87171', // red-400
        wordAddedBackground: '#047857', // emerald-700
        wordRemovedBackground: '#991b1b', // red-800
        lineNumberColor: '#52525b', // zinc-600
        emptyLineBackground: '#18181b', // zinc-900
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
          <div key={index} className="bg-zinc-950 border border-zinc-800 rounded-xl overflow-hidden shadow-lg">
            <button 
              onClick={() => toggleFile(diff.file)}
              className="w-full flex items-center justify-between p-3 bg-zinc-900/50 hover:bg-zinc-800/50 transition-colors border-b border-zinc-800"
            >
              <div className="flex items-center gap-3">
                <FileCode size={18} className={isNewFile ? "text-emerald-400" : "text-indigo-400"} />
                <span className="font-mono text-sm text-zinc-300">{diff.file}</span>
                {isNewFile && <Badge variant="success">New File</Badge>}
              </div>
              {isExpanded ? <ChevronUp size={18} className="text-zinc-500" /> : <ChevronDown size={18} className="text-zinc-500" />}
            </button>

            {isExpanded && (
              <div className="text-xs overflow-x-auto custom-scrollbar">
                <ReactDiffViewer
                  oldValue={diff.old_content}
                  newValue={diff.new_content}
                  splitView={true}
                  compareMethod={DiffMethod.WORDS}
                  useDarkTheme={true}
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