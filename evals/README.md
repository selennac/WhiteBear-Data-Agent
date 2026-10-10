# TextToSQL 评测

`cases/` 用于保存固定问数案例；`reports/` 用于本地评测输出。评测执行器和案例尚未实现。

后续评测固定参考时间、数据种子、Schema 和提示词版本，按查询结果比较正确性。工程 CI 使用模型桩；真实 Qwen 评测由配置 API Key 的开发者手动运行。

验收目标及覆盖范围见 [项目设计](../docs/project-design.md)。
