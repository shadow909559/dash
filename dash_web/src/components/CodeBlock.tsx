import { CopyButton } from "./CopyButton";

interface CodeBlockProps {
  code: string;
  language?: string;
}

export function CodeBlock({ code, language }: CodeBlockProps) {
  return (
    <div className="code-block">
      <CopyButton text={code} />
      <pre>
        <code>{code}</code>
      </pre>
      {language && (
        <span
          style={{
            position: "absolute",
            top: 8,
            left: 12,
            fontSize: 10,
            color: "var(--text-muted)",
            fontFamily: "var(--font-mono)",
            textTransform: "uppercase",
          }}
        >
          {language}
        </span>
      )}
    </div>
  );
}
