import React, { useRef, useEffect } from 'react';
import Editor, { OnMount } from '@monaco-editor/react';

interface MonacoViewerProps {
  value: string;
  language: string;
  readOnly?: boolean;
  onChange?: (value: string | undefined) => void;
  highlightRange?: [number, number] | null;
  height?: string | number;
  title?: string;
  badge?: string;
  sha256?: string;
}

export const MonacoViewer: React.FC<MonacoViewerProps> = ({
  value,
  language,
  readOnly = false,
  onChange,
  highlightRange,
  height = '100%',
  title,
  badge,
  sha256,
}) => {
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const decorationsRef = useRef<string[]>([]);

  const handleEditorDidMount: OnMount = (editor, monaco) => {
    editorRef.current = editor;
    monacoRef.current = monaco;

    // Apply initial decorations if range provided
    if (highlightRange) {
      applyHighlight(highlightRange[0], highlightRange[1]);
    }
  };

  const applyHighlight = (startLine: number, endLine: number) => {
    if (!editorRef.current || !monacoRef.current) return;

    const monaco = monacoRef.current;
    const editor = editorRef.current;

    const newDecorations = [
      {
        range: new monaco.Range(startLine, 1, endLine, 1),
        options: {
          isWholeLine: true,
          className: 'bg-sky-500/20 border-l-4 border-sky-400',
          linesDecorationsClassName: 'bg-sky-500 w-1.5',
        },
      },
    ];

    decorationsRef.current = editor.deltaDecorations(decorationsRef.current, newDecorations);
    editor.revealLineInCenter(startLine);
  };

  useEffect(() => {
    if (highlightRange) {
      applyHighlight(highlightRange[0], highlightRange[1]);
    } else if (editorRef.current) {
      decorationsRef.current = editorRef.current.deltaDecorations(decorationsRef.current, []);
    }
  }, [highlightRange]);

  return (
    <div className="flex flex-col h-full border border-slate-800 rounded-xl overflow-hidden bg-slate-900 shadow-md">
      {(title || badge || sha256) && (
        <div className="flex items-center justify-between px-4 py-2.5 bg-slate-850 border-b border-slate-800 text-xs">
          <div className="flex items-center gap-2">
            {badge && (
              <span className="px-2 py-0.5 rounded-full bg-slate-800 border border-slate-700 text-slate-300 font-mono text-[10px] uppercase font-semibold">
                {badge}
              </span>
            )}
            {title && <span className="font-semibold text-slate-200">{title}</span>}
          </div>

          {sha256 && (
            <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400 bg-slate-950/70 px-2.5 py-1 rounded border border-slate-800">
              <span className="text-slate-500">SHA-256:</span>
              <span className="text-sky-400 font-bold truncate max-w-[140px]" title={sha256}>
                {sha256.substring(0, 16)}...
              </span>
            </div>
          )}
        </div>
      )}

      <div className="flex-1 w-full relative min-h-[300px]">
        <Editor
          height={height}
          language={language}
          value={value}
          theme="vs-dark"
          onChange={onChange}
          onMount={handleEditorDidMount}
          options={{
            readOnly,
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            lineNumbersMinChars: 3,
            glyphMargin: true,
            automaticLayout: true,
            scrollBeyondLastLine: false,
            fontFamily: "'JetBrains Mono', Consolas, monospace",
            renderLineHighlight: 'all',
            padding: { top: 12, bottom: 12 },
          }}
        />
      </div>
    </div>
  );
};
