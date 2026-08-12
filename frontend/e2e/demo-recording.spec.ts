import {expect, test} from '@playwright/test';
import path from 'node:path';

const apiBaseUrl = process.env.SUPPORTFLOW_API_BASE_URL || 'http://localhost:8080';
const outputPath = path.resolve('../docs/demo/supportflow-demo.webm');

async function scene(page, title: string, detail: string, milliseconds = 7_000) {
  await page.evaluate(({title, detail}) => {
    document.querySelector('[data-demo-caption]')?.remove();
    const caption = document.createElement('section');
    caption.dataset.demoCaption = 'true';
    caption.style.cssText = 'position:fixed;left:32px;right:32px;bottom:28px;z-index:99999;padding:18px 22px;border-radius:16px;background:rgba(8,15,31,.92);color:#fff;box-shadow:0 18px 50px rgba(0,0,0,.35);font-family:system-ui,sans-serif';
    caption.innerHTML = `<strong style="display:block;font-size:20px;margin-bottom:6px">${title}</strong><span style="font-size:15px;color:#cbd5e1">${detail}</span>`;
    document.body.appendChild(caption);
  }, {title, detail});
  await page.waitForTimeout(milliseconds);
  await page.evaluate(() => document.querySelector('[data-demo-caption]')?.remove());
}

test('records the SupportFlow AI consumer-to-agent demo', async ({browser, request, baseURL}) => {
  test.setTimeout(300_000);
  const suffix = `${Date.now()}${Math.floor(Math.random() * 10_000)}`;
  const tenantCode = `demo-${suffix}`;
  const adminEmail = `admin-${suffix}@supportflow.test`;
  const password = 'safe-password-123';
  const tenant = await request.post(`${apiBaseUrl}/api/v1/tenants/register`, {
    data: {tenantCode, tenantName: 'SupportFlow 演示商城', email: adminEmail, displayName: '演示管理员', password},
  });
  expect(tenant.status()).toBe(201);

  const context = await browser.newContext({
    viewport: {width: 1440, height: 900},
    recordVideo: {dir: path.resolve('../docs/demo/raw'), size: {width: 1440, height: 900}},
  });
  const page = await context.newPage();
  const video = page.video();

  await page.goto(baseURL!);
  await scene(page, 'SupportFlow AI', '多租户电商售后 AI 客服：从消费者咨询到坐席闭环', 10_000);
  await page.getByRole('button', {name: '新用户？注册消费者账户'}).click();
  await scene(page, '消费者自助注册', '租户代码、账号和订单数据均限制在当前企业范围内');
  await page.getByLabel('租户代码').fill(tenantCode);
  await page.getByLabel('显示名称').fill('演示消费者');
  await page.getByLabel('邮箱').fill(`customer-${suffix}@supportflow.test`);
  await page.getByLabel('密码').fill(password);
  await scene(page, '安全登录', 'JWT 只保存在当前浏览器，后端从认证上下文派生 tenantId');
  await page.getByRole('button', {name: '注册并登录'}).click();
  await expect(page.getByRole('heading', {name: '我的订单与服务'})).toBeVisible();
  await expect(page.locator('.customer-ticket').first()).toBeVisible();
  await scene(page, '消费者服务台', '新账号自动获得隔离的演示订单，可直接发起售后咨询', 9_000);
  await page.locator('textarea').fill('我需要人工客服处理这个订单');
  await scene(page, '可靠流式会话', '消息使用幂等键提交，生成事件通过 SSE 增量推送并支持断线重放');
  await page.getByRole('button', {name: '发送消息'}).click();
  await expect(page.getByText('已转人工客服，坐席会继续处理该问题。')).toBeVisible();
  await scene(page, '自动转人工', '证据不足或模型失败时不自由回答，系统创建带 SLA 的工单', 10_000);

  await page.evaluate(() => {
    localStorage.removeItem('supportflow.accessToken');
    localStorage.removeItem('supportflow.refreshToken');
  });
  await page.reload();
  await scene(page, '切换到坐席视角', '同一个闭环继续由租户管理员处理，不跨越企业边界');
  await page.getByLabel('租户代码').fill(tenantCode);
  await page.getByLabel('邮箱').fill(adminEmail);
  await page.getByLabel('密码').fill(password);
  await page.getByRole('button', {name: '登录'}).click();
  await expect(page.getByText('SupportFlow AI')).toBeVisible();
  await scene(page, '运营概览', '集中查看工单、SLA、转人工和 AI 运行指标', 9_000);
  await page.getByRole('button', {name: '工单'}).click();
  await expect(page.getByRole('heading', {name: '工单协同'})).toBeVisible();
  await scene(page, '工单协同', '消费者请求已进入坐席队列，保留优先级和响应时限');
  await page.getByRole('button', {name: '认领工单'}).click();
  await expect(page.getByText('工单已认领，现可继续处理。')).toBeVisible();
  await scene(page, '认领与并发控制', '服务端校验工单状态，避免多个坐席重复认领');
  await page.getByLabel('内部备注').fill('已核对订单信息，正在为客户跟进。');
  await page.getByRole('button', {name: '保存内部备注'}).click();
  await expect(page.getByText('已核对订单信息，正在为客户跟进。')).toBeVisible();
  await scene(page, '协作记录', '内部备注进入审计链路，不会作为消费者公开消息发送');
  await page.getByRole('button', {name: '标记已解决'}).click();
  await expect(page.getByText('工单已标记为已解决。')).toBeVisible();
  await scene(page, '解决工单', '状态机限制非法跳转，并记录处理人与完成时间');
  await page.getByRole('button', {name: '关闭工单'}).click();
  await expect(page.getByText('工单已关闭。')).toBeVisible();
  await scene(page, '闭环完成', '消费者咨询、AI 分流、人工处理和工单关闭已完整贯通', 10_000);

  await page.getByRole('button', {name: '知识库', exact: true}).click();
  await scene(page, 'RAG 知识库', '文档摄取、分块、向量检索和引用均按 tenantId 隔离', 9_000);
  await page.getByRole('button', {name: '自动化'}).click();
  await scene(page, '高风险审批', '退款和补偿永远需要人工确认，再由 Outbox 与 RocketMQ 可靠执行', 10_000);
  await page.getByRole('button', {name: '分析'}).click();
  await expect(page.getByRole('heading', {name: 'SLA 与运营报表'})).toBeVisible();
  await scene(page, '质量与性能', 'Testcontainers、Playwright、JaCoCo 与 k6 共同组成交付门禁', 10_000);
  await scene(page, 'SupportFlow AI', '一个可测试、可恢复、可用 Docker Compose 启动的全栈 AI 应用', 35_000);

  await context.close();
  await video?.saveAs(outputPath);
});
