export const PAGE_SLOT_COUNT = 9;

export type PageSlot =
  | { kind: "page"; page: number }
  | { kind: "ellipsis" }
  | { kind: "empty" };

/**
 * Always returns exactly PAGE_SLOT_COUNT slots so the pager width never changes.
 * Layout: [1] [2] [··5 flexible··] [n-1] [n]
 */
export function getPageSlots(current: number, total: number): PageSlot[] {
  if (total <= 0) return [];

  if (total <= PAGE_SLOT_COUNT) {
    return Array.from({ length: total }, (_, i) => ({ kind: "page" as const, page: i + 1 }));
  }

  const slots: PageSlot[] = Array.from({ length: PAGE_SLOT_COUNT }, () => ({ kind: "empty" }));

  const innerLo = 3;
  const innerHi = total - 2;

  slots[0] = { kind: "page", page: 1 };
  slots[1] = { kind: "page", page: 2 };
  slots[7] = { kind: "page", page: total - 1 };
  slots[8] = { kind: "page", page: total };

  if (current <= innerLo + 2) {
    slots[2] = { kind: "page", page: 3 };
    slots[3] = { kind: "page", page: 4 };
    slots[4] = { kind: "page", page: 5 };
    slots[5] = { kind: "page", page: 6 };
    slots[6] = innerHi > 6 ? { kind: "ellipsis" } : { kind: "empty" };
  } else if (current >= innerHi - 2) {
    slots[2] = innerHi - 3 > innerLo ? { kind: "ellipsis" } : { kind: "empty" };
    slots[3] = { kind: "page", page: innerHi - 3 };
    slots[4] = { kind: "page", page: innerHi - 2 };
    slots[5] = { kind: "page", page: innerHi - 1 };
    slots[6] = { kind: "page", page: innerHi };
  } else {
    slots[2] = { kind: "ellipsis" };
    slots[3] = { kind: "page", page: current - 1 };
    slots[4] = { kind: "page", page: current };
    slots[5] = { kind: "page", page: current + 1 };
    slots[6] = { kind: "ellipsis" };
  }

  return slots;
}
