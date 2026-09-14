import { NextRequest } from "next/server";

import { proxyToApi } from "@/lib/proxy-api";

type RouteContext = { params: Promise<{ path: string[] }> };

async function handler(req: NextRequest, ctx: RouteContext) {
  const { path } = await ctx.params;
  return proxyToApi(req, `/api/${path.join("/")}`);
}

export const GET = handler;
export const POST = handler;
export const PUT = handler;
export const PATCH = handler;
export const DELETE = handler;
