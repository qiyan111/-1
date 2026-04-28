const metrics = [
  { label: "今日待处理批次", value: "0" },
  { label: "待审核结果", value: "0" },
  { label: "审计告警", value: "0" },
] as const;

export function DashboardPage() {
  return (
    <section className="dashboard">
      <header className="dashboard__header">
        <h1>系统看板</h1>
        <p>当前为工程骨架阶段，业务数据将在后续模块接入。</p>
      </header>
      <div className="dashboard__grid">
        {metrics.map((metric) => (
          <article className="metric" key={metric.label}>
            <div className="metric__label">{metric.label}</div>
            <div className="metric__value">{metric.value}</div>
          </article>
        ))}
      </div>
    </section>
  );
}

