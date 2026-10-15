import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
	title: "SearchIntel AI — Website intelligence",
	description:
		"Crawl, audit, explore, and ask evidence-grounded questions about your websites.",
};

export default function RootLayout({
	children,
}: Readonly<{ children: React.ReactNode }>) {
	return (
		<html lang="en">
			<body>{children}</body>
		</html>
	);
}
