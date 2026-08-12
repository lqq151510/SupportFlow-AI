import {fireEvent, render, screen} from '@testing-library/react';
import {vi} from 'vitest';
import {App} from './App.jsx';
import {getSession} from './api.js';

vi.mock('./api.js', async () => ({
  ...(await vi.importActual('./api.js')),
  getSession: vi.fn().mockResolvedValue(null),
  getOperationsOverview: vi.fn().mockResolvedValue(null),
  getTickets: vi.fn().mockResolvedValue([]),
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
  expect(screen.getByText('RAG 质量影响')).toBeInTheDocument();
});
