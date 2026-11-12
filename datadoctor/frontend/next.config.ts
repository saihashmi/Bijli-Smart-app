import type { NextConfig } from "next";

// The browser only ever calls /api on the same origin; Next.js forwards those requests to FastAPI.
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Must allow the backend's MAX_UPLOAD_MB plus multipart overhead, or Next.js silently truncates large uploads
// (its default body limit for proxied requests is 10 MB). The backend still enforces the real limit.
const maxUploadMb = Number(process.env.MAX_UPLOAD_MB ?? 20);

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: {
    middlewareClientMaxBodySize: `${maxUploadMb + 5}mb`,
    proxyTimeout: 120_000, // ms; profiling/export requests can take longer than the 30 s default
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
