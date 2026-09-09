import {fireEvent, render, screen} from '@testing-library/react';
import {afterEach, vi} from 'vitest';
import {App} from './App.jsx';
import {
  getBackendHealth,
  getKnowledgeBases,
  getKnowledgeDocuments,
  getModelConfigs,
  getModelUsageOverview,
  getMyProfile,
  getRecentModelUsages,
  getSession,
  getApprovals,
  getTickets,
  organizeKnowledgeDocument,
  refreshSession,
  updateModelConfig,
  updateMyProfile
} from './api.js';

vi.mock('./api.js', async () => ({
  ...(await vi.importActual('./api.js')),
  getSession: vi.fn().mockResolvedValue(null),
  refreshSession: vi.fn().mockRejectedValue(new Error('no refresh token')),
  getBackendHealth: vi.fn().mockResolvedValue({status: 'UP'}),
  getOperationsOverview: vi.fn().mockResolvedValue(null),
  getTickets: vi.fn().mockResolvedValue([]),
  getApprovals: vi.fn().mockResolvedValue([]),
  getTicketContext: vi.fn().mockResolvedValue({conversation:{messages:[],traces:[]},orders:[]}),
  getAssignableMembers: vi.fn().mockResolvedValue([]),
  getKnowledgeBases: vi.fn().mockResolvedValue([]),
  getKnowledgeDocuments: vi.fn().mockResolvedValue([]),
  createKnowledgeBase: vi.fn(),
  uploadKnowledgeDocument: vi.fn(),
  organizeKnowledgeDocument: vi.fn().mockResolvedValue({
    documentId: '9007199254740995',
    fileName: 'refund.md',
    summary: '退款核心规则说明',
    tags: ['退款', '售后'],
    modelUsed: 'deepseek-chat',
    totalTokens: 120,
    latencyMs: 350
  }),
  getModelConfigs: vi.fn().mockResolvedValue([]),
  createModelConfig: vi.fn(),
  updateModelConfig: vi.fn(),
  setDefaultModelConfig: vi.fn(),
  setKnowledgeDefaultModelConfig: vi.fn(),
  probeModelConnection: vi.fn(),
  getModelUsageOverview: vi.fn().mockResolvedValue({
    totalCalls: 12,
    totalInputTokens: 8400,
    totalOutputTokens: 2100,
    totalTokens: 10500,
    averageLatencyMs: 240,
    totalEstimatedCostCny: '0.0126',
    totalEstimatedCostUsd: '0.0017',
    scenarioCalls: {CHAT: 10, KNOWLEDGE_ORGANIZATION: 2},
    scenarioTokens: {CHAT: 9000, KNOWLEDGE_ORGANIZATION: 1500},
    modelTokens: {'deepseek-chat': 10500},
    modelCostCny: {'deepseek-chat': '0.0126'}
  }),
  getRecentModelUsages: vi.fn().mockResolvedValue([
    {
      id: '1',
      tenantId: '1',
      scenario: 'CHAT',
      modelName: 'deepseek-chat',
      protocol: 'STREAM',
      inputTokens: 800,
      outputTokens: 200,
      totalTokens: 1000,
      latencyMs: 210,
      estimatedCostCny: '0.0012',
      createdAt: '2026-08-29T10:00:00Z'
    }
  ]),
  getMyProfile: vi.fn().mockResolvedValue({displayName: 'Account Admin', email: 'account@example.test', role: 'TENANT_ADMIN', tenantName: '账户工作区', tenantCode: 'account-workspace', joinedAt: '2026-08-29T00:00:00Z'}),
  updateMyProfile: vi.fn(),
  changePassword: vi.fn(),
}));

afterEach(() => {
  localStorage.clear();
});

test('opens the workbench directly for guests and hosts sign-in in the personal center', async () => {
  vi.mocked(getSession).mockResolvedValueOnce(null);
  render(<App/>);

  // 访客也能看到完整工作台骨架，登录表单嵌在个人中心页内，而不是独立登录墙。
  expect(await screen.findByRole('heading', {name: '登录服务工作台'})).toBeInTheDocument();
  expect(screen.getByRole('button', {name: '概览'})).toBeInTheDocument();
  expect(screen.getByRole('button', {name: /工单/})).toBeInTheDocument();
  expect(screen.getAllByText('未登录').length).toBeGreaterThan(0);
});

test('restores the session silently via refresh token on startup', async () => {
  localStorage.setItem('supportflow.refreshToken', 'stored-refresh-token');
  vi.mocked(getSession).mockRejectedValueOnce(new Error('未登录')).mockResolvedValueOnce({role: 'TENANT_ADMIN'});
  vi.mocked(refreshSession).mockResolvedValueOnce({accessToken: 'next-access', refreshToken: 'next-refresh'});
  render(<App/>);

  expect(await screen.findByRole('heading', {name: '工作台总览'})).toBeInTheDocument();
  expect(refreshSession).toHaveBeenCalledWith('stored-refresh-token');
  expect(localStorage.getItem('supportflow.accessToken')).toBe('next-access');
  expect(localStorage.getItem('supportflow.refreshToken')).toBe('next-refresh');
});

test('switches between login and consumer registration modes', async () => {
  vi.mocked(getSession).mockResolvedValueOnce(null);
  render(<App/>);

  expect(await screen.findByRole('heading', {name: '登录服务工作台'})).toBeInTheDocument();
  expect(await screen.findByText('本地服务已连接')).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: '新用户？注册消费者账户'}));

  expect(screen.getByRole('heading', {name: '创建消费者账户'})).toBeInTheDocument();
  expect(screen.getByLabelText('显示名称')).toBeRequired();
  expect(screen.getByRole('button', {name: '注册并登录'})).toBeInTheDocument();
});

test('offers first-time users a workspace administrator registration flow', async () => {
  vi.mocked(getSession).mockResolvedValueOnce(null);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '首次使用？创建工作区'}));
  expect(screen.getByRole('heading', {name: '创建工作区管理员'})).toBeInTheDocument();
  expect(screen.queryByLabelText('租户代码')).not.toBeInTheDocument();
  expect(screen.queryByLabelText('工作区名称')).not.toBeInTheDocument();
  expect(screen.getByRole('button', {name: '创建并登录'})).toBeInTheDocument();
});

test('explains when the local backend is offline and can retry', async () => {
  vi.mocked(getSession).mockResolvedValueOnce(null);
  vi.mocked(getBackendHealth).mockRejectedValueOnce(new Error('offline')).mockResolvedValueOnce({status: 'UP'});
  render(<App/>);

  expect(await screen.findByText('本地服务未连接')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: '登录'})).toBeDisabled();
  fireEvent.click(screen.getByRole('button', {name: '重新检测'}));
  expect(await screen.findByText('本地服务已连接')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: '登录'})).toBeEnabled();
});

test('opens the analytics workspace without a runtime error', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '分析'}));
  expect(screen.getByRole('heading', {name: 'SLA 与运营报表'})).toBeInTheDocument();
  expect(screen.getByText('模型用量')).toBeInTheDocument();
  expect(screen.getByText('统计只包含已记录 latency_ms 的生成任务，不混入静态演示数据。')).toBeInTheDocument();
});

test('opens a matching ticket from the command-k global search', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  vi.mocked(getTickets).mockResolvedValueOnce([{id: '9007199254740999', title: '搜索目标退款工单', customerId: '42', priority: 'HIGH', status: 'NEW', resolutionDueAt: '2099-01-01T00:00:00Z'}]);
  render(<App/>);

  const search = await screen.findByRole('combobox', {name: '全局搜索工单'});
  fireEvent.keyDown(window, {key: 'k', metaKey: true});
  expect(search).toHaveFocus();
  fireEvent.change(search, {target: {value: '搜索目标'}});
  expect(await screen.findByRole('option', {name: /TKT-9007199254740999.*搜索目标退款工单/})).toBeInTheDocument();
  fireEvent.keyDown(search, {key: 'Enter'});

  expect(await screen.findByRole('heading', {name: '工单协同'})).toBeInTheDocument();
  expect(screen.getByRole('heading', {name: '搜索目标退款工单'})).toBeInTheDocument();
  expect(search).toHaveValue('');
});

test('derives the notification badge from current tickets and pending approvals', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'TENANT_ADMIN'});
  vi.mocked(getTickets).mockResolvedValueOnce([
    {id: '9007199254740991', title: '待跟进工单', customerId: '42', priority: 'NORMAL', status: 'OPEN', resolutionDueAt: '2099-01-01T00:00:00Z'},
    {id: '9007199254740992', title: '已关闭工单', customerId: '43', priority: 'LOW', status: 'CLOSED', resolutionDueAt: '2099-01-01T00:00:00Z'}
  ]);
  vi.mocked(getApprovals).mockResolvedValueOnce([{id: 'approval-1', status: 'PENDING'}]);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '查看通知'}));
  expect(await screen.findByText('当前工作区有 2 条待处理事项')).toBeInTheDocument();
  expect(screen.getByText('其中 1 条等待审批')).toBeInTheDocument();
  expect(screen.getByText('1 个未关闭工单')).toBeInTheDocument();
});

test('loads tenant knowledge bases and allows AI organizing', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  vi.mocked(getKnowledgeBases).mockResolvedValueOnce([{id: '9007199254740993', name: '退款政策库', description: '退款规则', status: 'ACTIVE'}]);
  vi.mocked(getKnowledgeDocuments).mockResolvedValueOnce([{id: '9007199254740995', fileName: 'refund.md', contentHash: 'abcdef0123456789abcdef', status: 'INDEXED'}]);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '知识库', exact: true}));
  expect(await screen.findByRole('button', {name: /退款政策库/})).toBeInTheDocument();
  expect(await screen.findByText('refund.md')).toBeInTheDocument();

  const organizeBtn = screen.getByRole('button', {name: '智能整理'});
  fireEvent.click(organizeBtn);

  expect(await screen.findByText(/文档智能整理报告/)).toBeInTheDocument();
  expect(screen.getByText('退款核心规则说明')).toBeInTheDocument();
});

test('loads model configurations without rendering API keys', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  vi.mocked(getModelConfigs).mockResolvedValueOnce([{id: '9007199254740997', name: '客服主模型', protocol: 'OPENAI_COMPATIBLE', baseUrl: 'https://api.deepseek.com/v1', modelName: 'deepseek-chat', isDefault: true, isKnowledgeDefault: true}]);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '设置'}));
  expect(await screen.findByText('客服主模型 · OPENAI_COMPATIBLE')).toBeInTheDocument();
  expect(screen.getByText(/API Key 采用 AES-GCM 加密，列表接口永不返回明文/)).toBeInTheDocument();
  expect(screen.queryByDisplayValue(/api-key/i)).not.toBeInTheDocument();
});

test('opens personal center with real cost estimation dashboard and in-place edit', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'TENANT_ADMIN'});
  vi.mocked(getMyProfile).mockResolvedValueOnce({displayName: 'Account Admin', email: 'account@example.test', role: 'TENANT_ADMIN', tenantName: '账户工作区', tenantCode: 'account-workspace', joinedAt: '2026-08-29T00:00:00Z'});
  vi.mocked(getModelConfigs).mockResolvedValueOnce([{id: '9007199254740998', name: '云端客服模型', protocol: 'OPENAI_COMPATIBLE', baseUrl: 'https://api.deepseek.com/v1', modelName: 'deepseek-chat', isDefault: true, isKnowledgeDefault: true}]);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '打开个人中心'}));
  fireEvent.click(await screen.findByRole('menuitem', {name: '个人中心'}));
  expect(await screen.findByRole('heading', {name: 'Account Admin'})).toBeInTheDocument();
  expect(screen.getByText('account@example.test')).toBeInTheDocument();
  expect(screen.getByText('真实 API 费用与 Token 归集看板')).toBeInTheDocument();
  expect(screen.getByRole('button', {name: '前往设置管理模型与通知'})).toBeInTheDocument();
});

test('toggles personal center via shortcut Cmd+,', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'TENANT_ADMIN'});
  render(<App/>);

  expect(await screen.findByRole('heading', {name: '工作台总览'})).toBeInTheDocument();

  // 按下 Cmd + , 呼出个人中心
  fireEvent.keyDown(window, {key: ',', metaKey: true});
  expect(await screen.findByRole('heading', {name: '真实 API 费用与 Token 归集看板'})).toBeInTheDocument();

  // 再次按下 Cmd + , 切回原工作台
  fireEvent.keyDown(window, {key: ',', metaKey: true});
  expect(await screen.findByRole('heading', {name: '工作台总览'})).toBeInTheDocument();
});

test('updates the displayed personal name using the profile API', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'TENANT_ADMIN'});
  vi.mocked(getMyProfile).mockResolvedValueOnce({displayName: 'Before Update', email: 'profile@example.test', role: 'TENANT_ADMIN', tenantName: '账户工作区', tenantCode: 'account-workspace', joinedAt: '2026-08-29T00:00:00Z'});
  vi.mocked(getModelConfigs).mockResolvedValueOnce([]);
  vi.mocked(updateMyProfile).mockResolvedValueOnce({displayName: 'After Update', email: 'profile@example.test', role: 'TENANT_ADMIN', tenantName: '账户工作区', tenantCode: 'account-workspace', joinedAt: '2026-08-29T00:00:00Z'});
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '打开个人中心'}));
  fireEvent.click(await screen.findByRole('menuitem', {name: '个人中心'}));
  fireEvent.click(await screen.findByRole('button', {name: '编辑资料'}));
  fireEvent.change(screen.getByLabelText('显示名称'), {target: {value: 'After Update'}});
  fireEvent.click(screen.getByRole('button', {name: '保存资料'}));

  expect(await screen.findByRole('heading', {name: 'After Update'})).toBeInTheDocument();
  expect(updateMyProfile).toHaveBeenCalledWith({displayName: 'After Update'});
});
