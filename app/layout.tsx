import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Video Factory",
  description: "Multiplique e edite vídeos curtos com uma fila inteligente.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}
