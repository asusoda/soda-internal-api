import axios from "axios";
import type { ApiError } from "./types";

// Shapes of the storefront API responses that more than one storefront page uses.

// A product from GET /api/storefront/<org>/products. The store routes omit the fields that are optional here.
export interface Product {
  id: number;
  name: string;
  description: string | null;
  price: number;
  stock: number;
  image_url: string | null;
  category?: string | null;
  organization_id?: number;
  created_at?: string | null;
  updated_at?: string | null;
}

// An order item. The member order routes add product_name.
export interface OrderItem {
  id: number;
  product_id: number;
  quantity: number;
  price_at_time: number;
  product_name?: string;
}

// An order from GET /api/storefront/<org>/orders or GET /api/storefront/<org>/members/orders.
// The member route omits the officer fields that are optional here.
export interface Order {
  id: number;
  user_id?: number;
  total_amount: number;
  status: string;
  message?: string | null;
  created_at: string;
  updated_at: string | null;
  organization_id?: number;
  user_name?: string;
  user_email?: string | null;
  items: OrderItem[];
}

// The error text of a failed request: the API error, then the API message, then the error message.
export function errorDetail(err: unknown): string | undefined {
  if (axios.isAxiosError<ApiError>(err)) {
    return err.response?.data?.error || err.response?.data?.message || err.message;
  }
  return err instanceof Error ? err.message : undefined;
}
