import type { NextConfig } from "next";

// Render's private network hands over "host:port" without a scheme
const RAW_API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";
const API_URL = /^https?:\/\//.test(RAW_API_URL) ? RAW_API_URL.replace(/\/$/, "") : `http://${RAW_API_URL}`;

const nextConfig: NextConfig = {
  agentRules: false,
  // the dev-only "N" badge sat bottom-left over the menu footer and the stage during demos
  devIndicators: false,
  // the /api rewrite proxy gives up after 30 s by default; the guide and uploads can take longer
  experimental: { proxyTimeout: 120_000 },
  // lets a phone on the same Wi-Fi open the dev server by IP (e.g. http://10.1.6.38:3000/app)
  allowedDevOrigins: ["10.*.*.*", "192.168.*.*", "172.*.*.*", "*.local"],
  turbopack: {
    root: process.cwd(),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    // Same-origin proxy so the partner session cookie never leaves this origin.
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/api-docs", destination: `${API_URL}/docs` },
      { source: "/openapi.json", destination: `${API_URL}/openapi.json` },
    ];
  },
};

export default nextConfig;
