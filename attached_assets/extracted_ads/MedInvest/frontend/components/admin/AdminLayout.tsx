import AdminNav from "@/components/admin/AdminNav";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 border-r md:block">
          <AdminNav />
        </aside>
        <div className="flex-1">
          <div className="md:hidden border-b">
            <AdminNav />
          </div>
          {children}
        </div>
      </div>
    </div>
  );
}
