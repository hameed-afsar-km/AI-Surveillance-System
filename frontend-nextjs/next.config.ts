import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "http://localhost:5050/:path*",
      },
      {
        source: "/stream",
        destination: "http://localhost:5050/stream",
      },
    ];
  },
};

export default nextConfig;
