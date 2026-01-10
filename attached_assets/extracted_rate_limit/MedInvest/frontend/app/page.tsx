export default function Home() {
  return (
    <main>
      <h2 style={{ marginTop: 0 }}>UI Scaffolds</h2>
      <ul>
        <li>
          <a href="/admin/verification">Admin verification queue</a>
        </li>
        <li>
          <a href="/deals/1">Deal detail + AI Analyst panel (example deal_id=1)</a>
        </li>
      </ul>
      <p style={{ maxWidth: 700, lineHeight: 1.5 }}>
        These pages assume the Flask backend is running on the same origin (or proxied) and that the user is authenticated
        via your existing Flask session cookie. If you deploy separately, set NEXT_PUBLIC_API_BASE.
      </p>
    </main>
  );
}
