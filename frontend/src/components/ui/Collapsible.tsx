import * as CollapsiblePrimitive from "@radix-ui/react-collapsible";
import { ChevronDown } from "lucide-react";

export function CollapsibleSection({
  title,
  defaultOpen = true,
  badge,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <CollapsiblePrimitive.Root defaultOpen={defaultOpen} className="group/collapsible">
      <CollapsiblePrimitive.Trigger className="flex w-full items-center justify-between rounded-md px-1 py-1 transition-colors hover:bg-[var(--bg-hover)]">
        <span className="section-label">{title}</span>
        <span className="flex items-center gap-1.5">
          {badge}
          <ChevronDown
            size={12}
            className="text-[var(--text-faint)] transition-transform duration-200 group-data-[state=open]/collapsible:rotate-180"
          />
        </span>
      </CollapsiblePrimitive.Trigger>
      <CollapsiblePrimitive.Content className="mt-2.5 overflow-hidden data-[state=closed]:animate-[collapse-up_0.2s_ease-out] data-[state=open]:animate-[collapse-down_0.2s_ease-out]">
        {children}
      </CollapsiblePrimitive.Content>
    </CollapsiblePrimitive.Root>
  );
}
