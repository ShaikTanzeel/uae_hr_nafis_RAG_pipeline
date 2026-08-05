import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "UAE HR & Nafis Copilot — Legal Compliance Suite",
  description:
    "AI-powered HR compliance assistant grounded in UAE Federal Decree-Law No. 33 of 2021, Cabinet Resolution No. 1 of 2022, and Nafis Cabinet Regulation No. 43 of 2025.",
  keywords: ["UAE Labour Law", "Emiratisation", "HR Compliance", "Nafis", "Qdrant RAG"],
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="h-full antialiased">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=Inter:wght@300;400;500;600;700;800&display=swap"
          rel="stylesheet"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined:opsz,wght,FILL,GRAD@24,400,0,0&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="h-full">{children}</body>
    </html>
  );
}
