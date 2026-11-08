import type { NextConfig } from "next";

const API_URL = process.env.API_URL ?? "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  agentRules: false,
  // the dev-only "N" badge sat bottom-left over the menu footer and the stage during demos
  devIndicators: false,
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
