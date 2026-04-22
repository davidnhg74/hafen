import type { Metadata } from "next";
import "./globals.css";
import Navigation from "./components/Navigation";

export const metadata: Metadata = {
  title: "Depart — Oracle to PostgreSQL Migration",
  description: "Escape Oracle licensing with AI-powered PL/SQL to PostgreSQL conversion",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <Navigation />
        <div className="min-h-screen">
          {children}
        </div>
      </body>
    </html>
  );
}
