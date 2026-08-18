import * as TooltipPrimitive from "@radix-ui/react-tooltip";

export function TooltipProvider({ children }: { children: React.ReactNode }) {
  return (
    <TooltipPrimitive.Provider delayDuration={300} skipDelayDuration={100}>
      {children}
    </TooltipPrimitive.Provider>
  );
}

export function Tooltip({
  content,
  children,
  side = "top",
}: {
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "right" | "bottom" | "left";
}) {
  return (
    <TooltipPrimitive.Root>
      <TooltipPrimitive.Trigger asChild>{children}</TooltipPrimitive.Trigger>
      <TooltipPrimitive.Portal>
        <TooltipPrimitive.Content
          side={side}
          sideOffset={6}
          className="z-50 rounded-md border px-2.5 py-1.5 text-[11px] shadow-lg animate-fade-in"
          style={{
            borderColor: "var(--border)",
            background: "var(--bg-raised)",
            color: "var(--text)",
          }}
        >
          {content}
          <TooltipPrimitive.Arrow
            className="fill-[var(--bg-raised)]"
            style={{ filter: "drop-shadow(0 1px 0 var(--border))" }}
          />
        </TooltipPrimitive.Content>
      </TooltipPrimitive.Portal>
    </TooltipPrimitive.Root>
  );
}
