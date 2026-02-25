interface PanelHeaderProps {
  title: string;
  subtitle: string;
  children?: React.ReactNode;
}

export default function PanelHeader({ title, subtitle, children }: PanelHeaderProps) {
  return (
    <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
      <div>
        <h2 className="text-lg font-semibold text-zinc-100">{title}</h2>
        <p className="text-xs text-zinc-500 mt-0.5">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}
