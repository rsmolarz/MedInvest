import React from "react";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: 20 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 16 }}>
            <a href="/" style={{ textDecoration: "none", color: "inherit" }}>
              <h1 style={{ margin: 0, fontSize: 20 }}>MedInvest</h1>
            </a>
            <nav style={{ display: "flex", gap: 12, fontSize: 14 }}>
              <a href="/admin/verification">Admin Verification</a>
              <a href="/deals/1">Deal (example)</a>
            </nav>
          </div>
          {children}
        </div>
      </body>
    </html>
  );
}
