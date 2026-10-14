# 证据与结果的绑定

建议所有本轮资料均放在一个 runs/<id>/ 下：plan/、solver/、judge/、solver-service/、judge-service/、model/、report/、bench-live/。其中 plan 包含原始数据、客户端源文件、提示词、solver/judge 配置与可选 runtime contract。

每个 solver 记录保存请求、原始 HTTP 响应、usage、finish_reason、耗时、状态及合同 hash。judge 记录额外保存其所评分 solver 记录的 SHA-256。run.json 冻结本次选择范围和配置，index.json 保存所有逐题文件 SHA-256。summary 校验上下游哈希及逐题绑定后生成统计。

receipt 读取 /v1/models、可选 /metrics，加上操作者提供的真实 argv 和日志，核对 dtype、TP/PP/DP/EP/DCP、disable_custom_all_reduce、gpu_memory_utilization、max_model_len、max_num_seqs、max_num_batched_tokens、prefix、chunked、speculative、eager、compile mode、cudagraph mode 和 capture sizes。字段证据等级保留，未观测到的字段不冒充已验证。环境变量、版本、模型完整 revision、镜像身份仍依赖真实外部证据；small-only 不能认证完整权重。

seal evidence 计算除 results/ 和 seal 文件以外所有文件的清单 hash。seal final 先确认该清单未变化，再记录结果表文件 hash。seal check 重算验证。不是数字签名、RFC8785 JCS 或可信时间证明；篡改者若同时重写全部哈希链，仍须靠外部保存的 manifest hash 才能发现。

预期 profile 和 model_artifact 是声明；actual argv/startup log 是提供的记录；HTTP 是客户端观测。不同来源要分清，冻结只能保留已收集的信息，不会补出缺失的历史证据。
