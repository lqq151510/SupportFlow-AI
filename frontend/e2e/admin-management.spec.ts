import {expect, test} from '@playwright/test';

test('first-time admin creates a workspace, then manages knowledge and model configuration', async ({page, baseURL}) => {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  const email = `admin-${suffix}@supportflow.test`;
  const password = 'safe-password-123';

  await page.goto(baseURL!);
  await expect(page.getByText('本地服务已连接')).toBeVisible();
  await page.getByRole('button', {name: '首次使用？创建工作区'}).click();
  await page.getByLabel('显示名称').fill('Admin UI');
  await page.getByLabel('邮箱').fill(email);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', {name: '创建并登录'}).click();

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

  await page.getByRole('button', {name: '打开个人中心'}).click();
  await expect(page.getByRole('heading', {name: 'Admin UI'})).toBeVisible();
  await expect(page.getByText(email)).toBeVisible();
  await expect(page.getByText('客服主模型')).toBeVisible();
  await expect(page.getByRole('button', {name: '管理模型 API'})).toBeVisible();
  await expect(page.getByText('e2e-test-only-key')).toHaveCount(0);

  await page.getByRole('button', {name: '编辑资料'}).click();
  await page.getByLabel('显示名称').fill('Admin UI Updated');
  await page.getByRole('button', {name: '保存资料'}).click();
  await expect(page.getByRole('heading', {name: 'Admin UI Updated'})).toBeVisible();
});
