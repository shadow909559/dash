import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeHighlight from 'rehype-highlight';
import 'highlight.js/styles/github-dark.css';

export function MarkdownMessage({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      rehypePlugins={[rehypeHighlight]}
      components={{
        code: (props) => {
          const { className, children } = props as { className?: string; children: React.ReactNode };

          const isInline = !className || !String(className).includes('language-');

          if (isInline) {
            return <code className={className}>{children}</code>;
          }

          return (
            <pre className={className}>
              <code>{children}</code>
            </pre>
          );
        },
      }}
    >
      {content}
    </ReactMarkdown>
  );
}


