import {expect, test} from '@playwright/test';

const apiBaseUrl = process.env.SUPPORTFLOW_API_BASE_URL || 'http://localhost:8080';

test('consumer handoff is claimed, documented, resolved and closed by an agent', async ({browser, request, baseURL}) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  const tenantCode = `e2e-${suffix}`;
  const adminEmail = `admin-${suffix}@supportflow.test`;
  const password = 'safe-password-123';
  const tenant = await request.post(`${apiBaseUrl}/api/v1/tenants/register`, {
    data: {tenantCode, tenantName: 'Playwright Shop', email: adminEmail, displayName: 'E2E Admin', password},
  });
  expect(tenant.status()).toBe(201);

  const customerContext = await browser.newContext();
  const customerPage = await customerContext.newPage();
  await customerPage.goto(baseURL!);
  await customerPage.getByRole('button', {name: '新用户？注册消费者账户'}).click();
  await customerPage.getByLabel('租户代码').fill(tenantCode);
  await customerPage.getByLabel('显示名称').fill('E2E Customer');
  await customerPage.getByLabel('邮箱').fill(`customer-${suffix}@supportflow.test`);
  await customerPage.getByLabel('密码').fill(password);
  await customerPage.getByRole('button', {name: '注册并登录'}).click();
  await expect(customerPage.getByRole('heading', {name: '我的订单与服务'})).toBeVisible();
  await expect(customerPage.locator('.customer-ticket').first()).toBeVisible();
  await customerPage.locator('textarea').fill('我需要人工客服处理这个订单');
  await customerPage.getByRole('button', {name: '发送消息'}).click();
  await expect(customerPage.getByText('已转人工客服，坐席会继续处理该问题。')).toBeVisible();

  const agentContext = await browser.newContext();
  const agentPage = await agentContext.newPage();
  await agentPage.goto(baseURL!);
  await agentPage.getByLabel('租户代码').fill(tenantCode);
  await agentPage.getByLabel('邮箱').fill(adminEmail);
  await agentPage.getByLabel('密码').fill(password);
  await agentPage.getByRole('button', {name: '登录'}).click();
  await agentPage.getByRole('button', {name: '工单'}).click();
  await expect(agentPage.getByRole('heading', {name: '工单协同'})).toBeVisible();
  await expect(agentPage.getByRole('heading', {name: 'customer request requires an agent'})).toBeVisible();
  await agentPage.getByRole('button', {name: '认领工单'}).click();
  await expect(agentPage.getByText('工单已认领，现可继续处理。')).toBeVisible();
  await agentPage.getByLabel('内部备注').fill('已核对订单信息，正在为客户跟进。');
  await agentPage.getByRole('button', {name: '保存内部备注'}).click();
  await expect(agentPage.getByText('已核对订单信息，正在为客户跟进。')).toBeVisible();
  await agentPage.getByRole('button', {name: '标记已解决'}).click();
  await expect(agentPage.getByText('工单已标记为已解决。')).toBeVisible();
  await agentPage.getByRole('button', {name: '关闭工单'}).click();
  await expect(agentPage.getByText('工单已关闭。')).toBeVisible();
  await expect(agentPage.getByText(/· 已关闭 · 优先级/)).toBeVisible();

  await customerContext.close();
  await agentContext.close();
});
