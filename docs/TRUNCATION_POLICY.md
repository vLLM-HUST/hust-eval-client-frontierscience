# 与 MMLU-Pro 对齐的截断统计口径

2026-10-13 用户明确要求：judge 8192 全量，截断按昨天 MMLU-Pro 的逻辑处理。

设置 judge 配置顶层 scoring_policy 为 mmlu_extract_first（默认仍为 strict_final）。
示例：examples/judge8192-mmlu.json。官方 Appendix B 提示词、Research ≥7 门槛不变。

- stop 或 length 都尝试答案提取。使用正文中首次完整独占一行的 VERDICT，符合昨天优先提取首个显式答案的原则。
- Research 提取 [0,10] 数值；Olympiad 提取 CORRECT/INCORRECT。不会采用自由数字或选项字母兜底，因为 FrontierScience 不是选择题。
- length 的最后一行若没有换行，不视为完整数值，避免把截断的 8.5 误读成 8。
- 多个不同 VERDICT 会标记，但仍使用首次完整值；不做总分纠正。
- 未提取到、非法数值或请求失败保留在全部题数分母中，计为未成功；同时分别报告 judge_invalid、judge_unresolved、judge_transport_failures、judge_truncated 和 judge_truncated_with_grade。
- 保留全部原始正文、结束原因、request/record SHA-256；这只是本地提取和统计口径，并非官方 FrontierScience 评分复现。judge 失败计为未成功也不等于已经证明 solver 答错。
- judge 固定 max_tokens=8192、temperature=0、seed=17，solver 固定 max_tokens=16384。不自动修改请求预算；服务若拒绝超长请求，单独计入失败。
