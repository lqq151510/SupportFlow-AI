const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8080';

export async function getOperationsOverview() {
  const token = localStorage.getItem('supportflow.accessToken');
  if (!token) throw new Error('请先登录以查看运营数据');
  const response = await fetch(`${API_BASE_URL}/api/v1/admin/operations/overview`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error(`运营数据加载失败 (${response.status})`);
  return response.json();
}
