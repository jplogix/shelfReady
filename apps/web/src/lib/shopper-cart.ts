export type ShopperItem = {
  store_product_id: string;
  slug: string;
  title: string;
  price: string;
  currency: string;
  quantity: number;
  image?: string | null;
};

const KEY = "sr_shopper_cart";

function read(): ShopperItem[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(KEY);
    const parsed = raw ? (JSON.parse(raw) as ShopperItem[]) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function write(items: ShopperItem[]) {
  window.localStorage.setItem(KEY, JSON.stringify(items));
  window.dispatchEvent(new Event("sr-cart"));
}

export function getShopperCart(): ShopperItem[] {
  return read();
}

export function addShopperItem(item: Omit<ShopperItem, "quantity">, quantity = 1): ShopperItem[] {
  const items = read();
  const existing = items.find((row) => row.store_product_id === item.store_product_id);
  if (existing) existing.quantity += quantity;
  else items.push({ ...item, quantity });
  write(items);
  return items;
}

export function shopperCount(items: ShopperItem[] = read()): number {
  return items.reduce((sum, item) => sum + item.quantity, 0);
}
