# 业务数据

`metrics/` 用于保存版本化的指标定义、同义词和业务关系；`generated/` 用于本地生成的数据摘要与产物。

生成逻辑位于 `backend/app/business/`，通过 `app.cli` 暴露命令。在 `backend/` 激活虚拟环境并配置四个数据库连接后运行：

```bash
python -m app.cli db init
python -m app.cli business generate --days 365 --orders 10000 --seed 42
```

已有数据需要显式加 `--reset`，仅在事务内替换本项目标记的七张受管表中的行。固定参考时间可使用 `--as-of 2026-10-08T12:00:00+08:00`；不固定参考时间则每次使用真实当前时间。六张业务表在 `whitebear_business` Schema 下，`dataset_info` 保存生成参数和汇总，结构接口只向分析页面暴露业务表。

`metrics/commerce.yaml` 定义四项指标口径、同义词、粒度和时间字段。生成过程中以 Decimal 表示金额，写入 PostgreSQL NUMERIC；各订单金额等于明细金额之和，累计退款不超过明细实付金额。生成结果包含近期订单，默认最近 30 天口径独立输出统计。

目标数据集包含客户、分类、商品、订单、订单明细和退款六张表。默认参考时间使用 Asia/Shanghai 当前时间，覆盖过去 365 天，随机种子为 42。具体时间、金额和重置规则见 [项目设计](../docs/project-design.md)。
