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
  return <DashboardView />;
}
