import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Smallest possible production image for Docker.
  output: "standalone",
};

export default nextConfig;
