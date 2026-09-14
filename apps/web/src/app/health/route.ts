import { NextRequest } from "next/server";

import { proxyToApi } from "@/lib/proxy-api";

export async function GET(req: NextRequest) {
  return proxyToApi(req, "/health");
}
