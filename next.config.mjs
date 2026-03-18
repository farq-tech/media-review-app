/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: "https://poi-api-eu.onrender.com/api/:path*",
      },
    ];
  },
};

export default nextConfig;
