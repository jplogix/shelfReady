export const CART_EVENT = "sr-cart";

export type CartCountItem = { quantity: number };

export function notifyCartChanged() {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new Event(CART_EVENT));
}

export function shopperCount(items: CartCountItem[]): number {
  return items.reduce((sum, item) => sum + item.quantity, 0);
}
