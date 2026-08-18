import * as SwitchPrimitive from "@radix-ui/react-switch";

interface Props {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  id?: string;
  disabled?: boolean;
}

export function Switch({ checked, onCheckedChange, id, disabled }: Props) {
  return (
    <SwitchPrimitive.Root
      id={id}
      checked={checked}
      onCheckedChange={onCheckedChange}
      disabled={disabled}
      className="relative h-5 w-9 shrink-0 cursor-pointer rounded-full border transition-colors duration-200 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
      style={{
        borderColor: checked ? "var(--accent)" : "var(--border-strong)",
        background: checked ? "var(--accent)" : "var(--bg-hover)",
        outlineColor: "var(--ring)",
      }}
    >
      <SwitchPrimitive.Thumb
        className="block h-3.5 w-3.5 translate-x-0.5 rounded-full bg-white shadow-sm transition-transform duration-200 data-[state=checked]:translate-x-[18px]"
      />
    </SwitchPrimitive.Root>
  );
}
