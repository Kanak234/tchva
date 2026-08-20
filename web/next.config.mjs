/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: {
    unoptimized: true,
  },
  // headers() and rewrites() are not supported with output: 'export'.
  // The frontend talks to the backend via absolute URLs (NEXT_PUBLIC_API_BASE)
  // instead of the Next.js rewrite proxy. CORS is handled by the backend.
};

export default nextConfig;
