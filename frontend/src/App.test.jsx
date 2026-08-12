import {fireEvent, render, screen} from '@testing-library/react';
import {vi} from 'vitest';
import {App} from './App.jsx';
import {getKnowledgeBases, getKnowledgeDocuments, getModelConfigs, getSession} from './api.js';

vi.mock('./api.js', async () => ({
  ...(await vi.importActual('./api.js')),
  getSession: vi.fn().mockResolvedValue(null),
  getOperationsOverview: vi.fn().mockResolvedValue(null),
  getTickets: vi.fn().mockResolvedValue([]),
  getKnowledgeBases: vi.fn().mockResolvedValue([]),
  getKnowledgeDocuments: vi.fn().mockResolvedValue([]),
  createKnowledgeBase: vi.fn(),
  uploadKnowledgeDocument: vi.fn(),
  getModelConfigs: vi.fn().mockResolvedValue([]),
  createModelConfig: vi.fn(),
  probeModelConnection: vi.fn(),
}));

test('switches between login and consumer registration modes', async () => {
  vi.mocked(getSession).mockResolvedValueOnce(null);
  render(<App/>);

  expect(await screen.findByRole('heading', {name: '登录服务工作台'})).toBeInTheDocument();
  fireEvent.click(screen.getByRole('button', {name: '新用户？注册消费者账户'}));

  expect(screen.getByRole('heading', {name: '创建消费者账户'})).toBeInTheDocument();
  expect(screen.getByLabelText('显示名称')).toBeRequired();
  expect(screen.getByRole('button', {name: '注册并登录'})).toBeInTheDocument();
});

test('opens the analytics workspace without a runtime error', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '分析'}));
  expect(screen.getByRole('heading', {name: 'SLA 与运营报表'})).toBeInTheDocument();
  expect(screen.getByText('模型用量')).toBeInTheDocument();
  expect(screen.getByText('统计只包含已记录 latency_ms 的生成任务，不混入静态演示数据。')).toBeInTheDocument();
});

test('loads tenant knowledge bases and their real document catalog', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  vi.mocked(getKnowledgeBases).mockResolvedValueOnce([{id: '9007199254740993', name: '退款政策库', description: '退款规则', status: 'ACTIVE'}]);
  vi.mocked(getKnowledgeDocuments).mockResolvedValueOnce([{id: '9007199254740995', fileName: 'refund.md', contentHash: 'abcdef0123456789abcdef', status: 'INDEXED'}]);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '知识库', exact: true}));
  expect(await screen.findByRole('button', {name: /退款政策库/})).toBeInTheDocument();
  expect(await screen.findByText('refund.md')).toBeInTheDocument();
  expect(screen.getByText('已索引')).toBeInTheDocument();
});

test('loads model configurations without rendering API keys', async () => {
  vi.mocked(getSession).mockResolvedValueOnce({role: 'ADMIN'});
  vi.mocked(getModelConfigs).mockResolvedValueOnce([{id: '9007199254740997', name: '客服主模型', protocol: 'OPENAI_COMPATIBLE', baseUrl: 'https://api.example.com/v1', modelName: 'support-model', isDefault: true}]);
  render(<App/>);

  fireEvent.click(await screen.findByRole('button', {name: '设置'}));
  expect(await screen.findByText('客服主模型 · OPENAI_COMPATIBLE')).toBeInTheDocument();
  expect(screen.getByText('API Key 使用 AES-GCM 加密，列表接口永不返回明文。')).toBeInTheDocument();
  expect(screen.queryByDisplayValue(/api-key/i)).not.toBeInTheDocument();
});
