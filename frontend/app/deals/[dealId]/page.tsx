import AiAnalystPanel from "@/components/AiAnalystPanel";
import DealDetail from "@/components/DealDetail";

export default function DealDetailPage({ params }: { params: { dealId: string } }) {
  const dealId = Number(params.dealId);
  return (
    <main style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 16 }}>
      <div>
        <DealDetail dealId={dealId} />
      </div>
      <div>
        <AiAnalystPanel dealId={dealId} />
      </div>
    </main>
  );
}
