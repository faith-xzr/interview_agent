import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";

export function PageTitle({
  icon: Icon,
  title,
  subtitle,
  action
}: {
  icon: LucideIcon;
  title: string;
  subtitle: string;
  action?: ReactNode;
}) {
  return (
    <header className="workspace-title">
      <div className="workspace-title-main">
        <Icon size={32} aria-hidden="true" />
        <div>
          <h1>{title}</h1>
          <p>{subtitle}</p>
        </div>
      </div>
      {action ? <div className="workspace-title-action">{action}</div> : null}
    </header>
  );
}
