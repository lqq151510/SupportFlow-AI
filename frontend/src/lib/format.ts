// 通用格式化与展示辅助。

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}`;
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "—";
  const diff = Date.now() - d;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "刚刚";
  if (min < 60) return `${min} 分钟前`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr} 小时前`;
  const day = Math.floor(hr / 24);
  return `${day} 天前`;
}

const STATUS_LABELS: Record<string, { label: string; cls: string }> = {
  OPEN: { label: "处理中", cls: "badge-warning" },
  CLOSED: { label: "已关闭", cls: "badge-success" },
  QUEUED: { label: "排队中", cls: "badge-info" },
  RUNNING: { label: "运行中", cls: "badge-info" },
  WAITING_APPROVAL: { label: "待审批", cls: "badge-warning" },
  COMPLETED: { label: "已完成", cls: "badge-success" },
  NEEDS_HUMAN: { label: "转人工", cls: "badge-danger" },
  FAILED: { label: "失败", cls: "badge-danger" },
  PENDING: { label: "待处理", cls: "badge-warning" },
  APPROVED: { label: "已批准", cls: "badge-success" },
  REJECTED: { label: "已拒绝", cls: "badge-danger" },
  EXPIRED: { label: "已过期", cls: "badge-danger" },
  ACTIVE: { label: "当前版本", cls: "badge-primary" },
  PUBLISHED: { label: "已发布", cls: "badge-success" },
  ARCHIVED: { label: "历史版本", cls: "badge" },
};

export function statusBadge(status: string | null | undefined): { label: string; cls: string } {
  if (!status) return { label: "—", cls: "badge" };
  return STATUS_LABELS[status] ?? { label: status, cls: "badge" };
}

const CATEGORY_LABELS: Record<string, string> = {
  delivery: "配送物流",
  return_refund: "退换货政策",
  product_usage: "商品使用",
  account: "账号问题",
  complaint: "投诉建议",
  other: "其他",
};

export function categoryLabel(category: string | null | undefined): string {
  if (!category) return "未分类";
  return CATEGORY_LABELS[category] ?? category;
}

const ROLE_LABELS: Record<string, string> = {
  USER: "客户",
  AGENT: "坐席",
  ADMIN: "管理员",
};

export function roleLabel(role: string | null | undefined): string {
  if (!role) return "—";
  return ROLE_LABELS[role] ?? role;
}
