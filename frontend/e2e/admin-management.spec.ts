import {expect, test} from '@playwright/test';

const apiBaseUrl = process.env.SUPPORTFLOW_API_BASE_URL || 'http://localhost:8080';

test('admin creates a knowledge base, uploads a document and saves a model config', async ({page, request, baseURL}) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  const tenantCode = `admin-ui-${suffix}`;
  const email = `admin-${suffix}@supportflow.test`;
  const password = 'safe-password-123';
  const tenant = await request.post(`${apiBaseUrl}/api/v1/tenants/register`, {
    data: {tenantCode, tenantName: 'Admin UI Shop', email, displayName: 'Admin UI', password},
  });
  expect(tenant.status()).toBe(201);

  await page.goto(baseURL!);
  await page.getByLabel('租户代码').fill(tenantCode);
  await page.getByLabel('邮箱').fill(email);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', {name: '登录'}).click();

  await page.getByRole('button', {name: '知识库', exact: true}).click();
  await expect(page.getByRole('heading', {name: '知识库管理'})).toBeVisible();
  await page.getByLabel('名称').fill('退款政策库');
  await page.getByLabel('描述').fill('退款与退货资格规则');
  await page.getByRole('button', {name: '创建知识库'}).click();
  await expect(page.getByRole('button', {name: /退款政策库/})).toBeVisible();

  await page.locator('input[type=file]').setInputFiles({
    name: 'refund-policy.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 退款政策\n符合条件的订单可在 30 天内申请退款。'),
  });
  await expect(page.getByText('refund-policy.md', {exact: true})).toBeVisible();
  await expect(page.getByText(/向量化中|已索引/)).toBeVisible();

  await page.getByRole('button', {name: '设置'}).click();
  await expect(page.getByRole('heading', {name: '模型配置', exact: true})).toBeVisible();
  await page.getByLabel('配置名称').fill('客服主模型');
  await page.getByLabel('Base URL').fill('https://api.example.com/v1');
  await page.getByLabel('模型名称').fill('support-model');
  await page.getByLabel('API Key').fill('e2e-test-only-key');
  await page.getByRole('button', {name: '保存配置'}).click();
  await expect(page.getByText('客服主模型 · OPENAI_COMPATIBLE')).toBeVisible();
  await expect(page.getByText('模型配置已加密保存。')).toBeVisible();
  await expect(page.getByLabel('API Key')).toHaveValue('');
});
