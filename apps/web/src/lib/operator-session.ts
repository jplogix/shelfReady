import { createHmac, timingSafeEqual } from "crypto";
import { NextRequest, NextResponse } from "next/server";

import { operatorAccessToken } from "./server-config";

export const SESSION_COOKIE = "sr_operator";

function sessionSecret(): string {
  return process.env.OPERATOR_SESSION_SECRET || operatorAccessToken();
}

export function signSession(): string {
  return createHmac("sha256", sessionSecret()).update("operator").digest("hex");
}

export function hasValidSession(req: NextRequest): boolean {
  const cookie = req.cookies.get(SESSION_COOKIE)?.value;
  if (!cookie) return false;
  const expected = signSession();
  const a = Buffer.from(cookie);
  const b = Buffer.from(expected);
  return a.length === b.length && timingSafeEqual(a, b);
}

export function isLocalDevelopment(req: NextRequest): boolean {
  if (process.env.NODE_ENV === "production") return false;
  const host = req.nextUrl.hostname;
  return host === "localhost" || host === "127.0.0.1";
}

export function applySessionCookie(res: NextResponse): NextResponse {
  res.cookies.set(SESSION_COOKIE, signSession(), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: 60 * 60 * 12,
  });
  return res;
}

export function clearSessionCookie(res: NextResponse): NextResponse {
  res.cookies.set(SESSION_COOKIE, "", { httpOnly: true, path: "/", maxAge: 0 });
  return res;
}

export function isPublicApiPath(path: string): boolean {
  if (path === "/api/session" || path === "/api/health" || path === "/health") return true;
  if (path === "/api/mode") return true;
  if (path.startsWith("/api/store/products")) return true;
  if (path.startsWith("/api/store/cart")) return true;
  if (path.startsWith("/api/media/")) return true;
  return false;
}
