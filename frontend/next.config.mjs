/** Static export: the Python server serves these files and the API from one address. */
const nextConfig = { output: 'export', images: { unoptimized: true }, trailingSlash: false, reactStrictMode: true };
export default nextConfig;
