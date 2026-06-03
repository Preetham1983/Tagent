import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ComponentPropsWithoutRef } from "react";

type Props = { content: string };

const components: Components = {
  img({ src, alt }: ComponentPropsWithoutRef<"img">) {
    return (
      <img
        src={src}
        alt={alt ?? ""}
        className="md-avatar"
        loading="lazy"
        referrerPolicy="no-referrer"
      />
    );
  },
  a({ href, children }: ComponentPropsWithoutRef<"a">) {
    return (
      <a href={href} target="_blank" rel="noopener noreferrer">
        {children}
      </a>
    );
  },
  code({ children, className }: ComponentPropsWithoutRef<"code">) {
    const isBlock = className?.startsWith("language-");
    return isBlock ? (
      <pre className="md-pre">
        <code className={className}>{children}</code>
      </pre>
    ) : (
      <code className="md-inline-code">{children}</code>
    );
  },
  p({ children }: ComponentPropsWithoutRef<"p">) {
    return <p className="md-p">{children}</p>;
  },
  ul({ children }: ComponentPropsWithoutRef<"ul">) {
    return <ul className="md-ul">{children}</ul>;
  },
  ol({ children }: ComponentPropsWithoutRef<"ol">) {
    return <ol className="md-ol">{children}</ol>;
  },
  li({ children }: ComponentPropsWithoutRef<"li">) {
    return <li className="md-li">{children}</li>;
  },
  h1({ children }: ComponentPropsWithoutRef<"h1">) {
    return <h1 className="md-h1">{children}</h1>;
  },
  h2({ children }: ComponentPropsWithoutRef<"h2">) {
    return <h2 className="md-h2">{children}</h2>;
  },
  h3({ children }: ComponentPropsWithoutRef<"h3">) {
    return <h3 className="md-h3">{children}</h3>;
  },
  hr() {
    return <hr className="md-hr" />;
  },
  table({ children }: ComponentPropsWithoutRef<"table">) {
    return (
      <div className="md-table-wrapper">
        <table className="md-table">{children}</table>
      </div>
    );
  },
  th({ children }: ComponentPropsWithoutRef<"th">) {
    return <th className="md-th">{children}</th>;
  },
  td({ children }: ComponentPropsWithoutRef<"td">) {
    return <td className="md-td">{children}</td>;
  },
};

export function MarkdownMessage({ content }: Props) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
      {content}
    </ReactMarkdown>
  );
}
