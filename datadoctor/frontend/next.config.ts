import type { NextConfig } from "next";

// The browser only ever calls /api on the same origin; Next.js forwards those requests to FastAPI.
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

// Must allow the backend's MAX_UPLOAD_MB plus multipart overhead, or Next.js silently truncates large uploads
// (its default body limit for proxied requests is 10 MB). The backend still enforces the real limit.
const maxUploadMb = Number(process.env.MAX_UPLOAD_MB ?? 20);

// Everything the pages need is served from this origin: no external scripts, fonts, images or API calls.
// Inline scripts/styles are needed by Next.js and the theme switcher; eval only by the development server.
const dev = process.env.NODE_ENV !== "production";
const csp = [
  "default-src 'self'",
  `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  `connect-src 'self'${dev ? " ws:" : ""}`,
  "worker-src 'self' blob:",
  "object-src 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const securityHeaders = [
  { key: "Content-Security-Policy", value: csp },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=(), payment=()" },
];

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  experimental: {
    middlewareClientMaxBodySize: `${maxUploadMb + 5}mb`,
    proxyTimeout: 120_000, // ms; profiling/export requests can take longer than the 30 s default
  },
  async headers() {
    return [{ source: "/((?!api/).*)", headers: securityHeaders }];
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backendUrl}/api/:path*` }];
  },
};

export default nextConfig;
