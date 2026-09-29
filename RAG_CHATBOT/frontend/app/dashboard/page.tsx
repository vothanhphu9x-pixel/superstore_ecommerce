import DashboardView from "@/components/dashboard/DashboardView";

export const metadata = {
  title: "Dashboard · Superstore Analytics",
};

/*
 * Bắt buộc dynamic vì cờ bảo mật được đọc lúc runtime.
 * Nếu prerender lúc build, trạng thái locked/unlocked có thể bị bake vào image.
 */
export const dynamic = "force-dynamic";

export default function DashboardPage() {
  const previewEnabled =
    process.env.ALLOW_UNAUTHENTICATED_INTERNAL_UI === "true";

  if (!previewEnabled) {
    return (
      <main className="mx-auto flex min-h-screen max-w-xl items-center px-6">
        <section className="rounded-2xl border border-slate-200 bg-white p-8 shadow-sm">
          <p className="text-sm font-medium text-indigo-600">
            Internal dashboard
          </p>

          <h1 className="mt-2 text-2xl font-semibold text-slate-950">
            Dashboard đang được khóa
          </h1>

          <p className="mt-3 text-slate-600">
            Staff authentication chưa được triển khai. Chỉ bật local preview
            bằng ALLOW_UNAUTHENTICATED_INTERNAL_UI=true trên máy phát triển.
          </p>
        </section>
      </main>
    );
  }

  return <DashboardView />;
}
