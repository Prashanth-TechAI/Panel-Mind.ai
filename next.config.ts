import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Next 16 only trusts "localhost" for dev resources; opening the app on
  // 127.0.0.1 gets /_next/* blocked as cross-origin, which silently kills HMR
  // *and* hydration — the page renders but no client JS ever attaches.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
