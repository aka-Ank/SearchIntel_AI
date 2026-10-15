import type { NextConfig } from "next";

const backend = process.env.SEARCHINTEL_API_ORIGIN ?? "http://127.0.0.1:8000";
const nextConfig: NextConfig = {
	async rewrites() {
		return [
			{ source: "/api-proxy/:path*", destination: `${backend}/api/v1/:path*` },
		];
	},
};

export default nextConfig;
