import AdminVerificationReview from "@/components/AdminVerificationReview";

export default function VerificationReviewPage({ params }: { params: { userId: string } }) {
  const userId = Number(params.userId);
  return (
    <main>
      <AdminVerificationReview userId={userId} />
    </main>
  );
}
