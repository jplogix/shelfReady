import { NextRequest, NextResponse } from "next/server";

import { applySessionCookie, clearSessionCookie, hasValidSession } from "@/lib/operator-session";
import { operatorAccessToken } from "@/lib/server-config";

export async function GET(req: NextRequest) {
  return NextResponse.json({ authenticated: hasValidSession(req) });
}

export async function POST(req: NextRequest) {
  const body = (await req.json().catch(() => ({}))) as { token?: string };
  const expected = operatorAccessToken();
  if (!body.token || body.token !== expected) {
    return NextResponse.json({ error: "invalid_operator_token" }, { status: 401 });
  }
  return applySessionCookie(NextResponse.json({ authenticated: true }));
}

export async function DELETE() {
  return clearSessionCookie(NextResponse.json({ authenticated: false }));
}
