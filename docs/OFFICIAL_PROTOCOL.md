# v0.2.0 官方提示词协议

来源：Wang et al., FrontierScience: Evaluating AI’s Ability to Perform Expert-Level Scientific Tasks, arXiv:2601.21165v1，附录 B 第13–14页，CC BY 4.0。https://arxiv.org/abs/2601.21165v1

远程下载 PDF SHA-256：a11077ec358612db1098b715c7631fd249e4b909afda5716fb573ffcc0663cfe。

代码 official_prompts.py 保存转录文本：合并 PDF 换行、还原 compound 的跨行断词、统一引号和占位符字符；保留原文 attemped 拼写。它是排版规范化转录，不声称与PDF文本字节完全相同。原文 <total_points> 被 PDF 提取器显示为 ¡total˙points¿，已恢复为可读占位符。提示词用单条 user 消息发送；论文未公开角色封装，该选择明确记录在合同中。

Olympiad 最后一行 VERDICT: CORRECT / INCORRECT。Research 先解释 rubric，再以 VERDICT: 数值结束。解析器只读最后一行，不从正文任意提取数字，不接受自定义JSON。Research范围0–10，>=7为成功。

分数与解释矛盾仅记 audit_flags，不改最终分数。程序对明确的 Total score/Total points 声明及简单加法等式做保守诊断，不能发现所有语义矛盾，仍需复核。原始分数与诊断必须一起报告。

相对官方实验的差异：judge=Qwen3.5-35B-A3B，thinking=false、max_tokens4096、temperature0、seed17；单次试验。官方是GPT-5 high并多次取平均，因此本结果是“官方提示词，替换judge模型的内部评测”，不是官方成绩复现。

本轮solver max_tokens16384。此前v0.1.0自定义JSON试验已封存，不重写。旧计划须使用归档源码；新源码校验会拒绝旧计划。
