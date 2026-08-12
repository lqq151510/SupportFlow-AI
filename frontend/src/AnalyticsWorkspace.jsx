import React from 'react';

const integer = value => Number(value || 0).toLocaleString();
const percent = value => `${(Number(value || 0) * 100).toFixed(1)}%`;

export function AnalyticsWorkspace({overview}) {
  const data = overview || {completedGenerations: 0, handoffGenerations: 0, aiResolutionRate: 0, overdueTickets: 0, inputTokens: 0, outputTokens: 0, averageGenerationLatencyMs: 0};
  const terminal = Number(data.completedGenerations) + Number(data.handoffGenerations);
  const handoffRate = terminal ? Number(data.handoffGenerations) / terminal : 0;
  return <>
    <div className="page-header"><div><h1>SLA 与运营报表</h1><p>来自当前租户真实生成任务与工单数据</p></div></div>
    <div className="stats"><div className="stat"><span>AI 已解决</span><strong>{integer(data.completedGenerations)}</strong><small>已完成生成任务</small></div><div className="stat"><span>AI 解决率</span><strong>{percent(data.aiResolutionRate)}</strong><small>按终态生成统计</small></div><div className="stat"><span>转人工率</span><strong>{percent(handoffRate)}</strong><small>{integer(data.handoffGenerations)} 次转人工</small></div><div className="stat"><span>SLA 违规工单</span><strong className="danger">{integer(data.overdueTickets)}</strong><small>未解决且已逾期</small></div></div>
    <div className="grid two"><section className="panel"><div className="panel-head"><h2>模型用量</h2><span className="status success">租户隔离</span></div><div className="quality vertical"><div><span>输入 Token</span><strong>{integer(data.inputTokens)}</strong><div className="progress"><span style={{width: `${Math.min(100, Number(data.inputTokens) / Math.max(1, Number(data.inputTokens) + Number(data.outputTokens)) * 100)}%`}}/></div></div><div><span>输出 Token</span><strong>{integer(data.outputTokens)}</strong><div className="progress purple"><span style={{width: `${Math.min(100, Number(data.outputTokens) / Math.max(1, Number(data.inputTokens) + Number(data.outputTokens)) * 100)}%`}}/></div></div></div></section><section className="panel"><div className="panel-head"><h2>生成性能</h2></div><div className="health-big"><strong>{integer(data.averageGenerationLatencyMs)} ms</strong><span>平均模型生成延迟</span></div><p className="safe-note">统计只包含已记录 latency_ms 的生成任务，不混入静态演示数据。</p></section></div>
  </>;
}
