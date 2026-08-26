import { ReactNode } from "react";

const INLINE = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  return text.split(INLINE).map((part, i) => {
    const key = `${keyPrefix}-${i}`;
    if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
      return <strong key={key}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*") && part.length > 2) {
      return <em key={key}>{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`") && part.length > 2) {
      return (
        <code
          key={key}
          style={{
            background: "rgba(0,0,0,0.06)",
            borderRadius: 4,
            padding: "1px 5px",
            fontSize: "0.9em",
          }}
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <span key={key}>{part}</span>;
  });
}

export function MarkdownLite({ text }: { text: string }) {
  const lines = text.split("\n");
  return (
    <>
      {lines.map((line, i) => {
        const key = `line-${i}`;
        const heading = line.match(/^#{1,6}\s+(.*)$/);
        if (heading) {
          return (
            <div key={key} style={{ fontWeight: 700, marginTop: i ? 8 : 0 }}>
              {renderInline(heading[1], key)}
            </div>
          );
        }
        if (!line.trim()) {
          return <div key={key} style={{ height: 8 }} />;
        }
        return <div key={key}>{renderInline(line, key)}</div>;
      })}
    </>
  );
}
