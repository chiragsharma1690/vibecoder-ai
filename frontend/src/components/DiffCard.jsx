import { useState } from 'react';
import ReactDiffViewer, { DiffMethod } from 'react-diff-viewer-continued';
import { FileCode, ChevronDown, ChevronUp } from 'lucide-react';

export default function DiffCard({ diffs }) {
  // Keep track of which files are expanded in the UI
  const [expandedFiles, setExpandedFiles] = useState(
    // Default to expanding the first file
    diffs.reduce((acc, curr, idx) => ({ ...acc, [curr.file]: idx === 0 }), {})
  );

  const toggleFile = (filename) => {
    setExpandedFiles(prev => ({ ...prev, [filename]: !prev[filename] }));
  };

  // Custom styling for the diff viewer to match our dark theme
  const customStyles = {
    variables: {
      dark: {
        diffViewerBackground: '#0f172a', // slate-900
        diffViewerColor: '#cbd5e1', // slate-300
        addedBackground: '#064e3b', // emerald-900
        addedColor: '#34d399', // emerald-400
        removedBackground: '#7f1d1d', // red-900
        removedColor: '#f87171', // red-400
        wordAddedBackground: '#047857', // emerald-700
        wordRemovedBackground: '#991b1b', // red-800
        lineNumberColor: '#475569', // slate-600
        emptyLineBackground: '#1e293b', // slate-800
      }
    }
  };

  if (!diffs || diffs.length === 0) return null;

  return (
    <div className="mt-4 space-y-4 w-full max-w-4xl">
      {diffs.map((diff, index) => {
        const isExpanded = expandedFiles[diff.file];
        const isNewFile = !diff.old_content && diff.new_content;

        return (
          <div key={index} className="bg-slate-900 border border-slate-700 rounded-lg overflow-hidden shadow-lg">
            {/* File Header (Clickable to expand/collapse) */}
            <button 
              onClick={() => toggleFile(diff.file)}
              className="w-full flex items-center justify-between p-3 bg-slate-800/80 hover:bg-slate-700/80 transition-colors border-b border-slate-700"
            >
              <div className="flex items-center gap-2">
                <FileCode size={18} className={isNewFile ? "text-emerald-400" : "text-blue-400"} />
                <span className="font-mono text-sm text-slate-200">{diff.file}</span>
                {isNewFile && (
                  <span className="text-[10px] uppercase font-bold bg-emerald-900/50 text-emerald-400 px-2 py-0.5 rounded ml-2">
                    New File
                  </span>
                )}
              </div>
              {isExpanded ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
            </button>

            {/* Diff Viewer Body */}
            {isExpanded && (
              <div className="text-xs overflow-x-auto">
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
}