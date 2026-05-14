import type { NextConfig } from "next";

function normalizeApiProxyTarget(value: string | undefined): string | null {
  const trimmed = value?.trim();
  if (!trimmed) {
    return null;
  }
  return trimmed.replace(/\/+$/, "");
}

const apiProxyTarget = normalizeApiProxyTarget(process.env.API_PROXY_TARGET);

const nextConfig: NextConfig = {
  devIndicators: false,
  async rewrites() {
    if (!apiProxyTarget) {
      return [];
    }

    return [
      {
        source: "/api/:path*",
        destination: `${apiProxyTarget}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
