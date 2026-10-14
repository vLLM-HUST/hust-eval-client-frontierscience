# hust-eval-client-frontierscience

连接**已经启动**的 OpenAI-compatible vLLM 服务，完成 FrontierScience 答题、Qwen judge 评分、性能压测和证据封存。纯 Python 标准库客户端，Python >=3.9；不启动、停止或修改 vLLM 服务，不依赖 PyramidKV 或 MMLU-Pro 项目。

当前示例的 solver 和 judge 都使用 **Qwen3.5-35B-A3B**（served name `qwen3.5-35b`），顺序执行，可以复用同一服务。两角色的 URL、模型名、采样参数、并发和超时独立配置。API key 只从环境变量读取，不写入计划。

## 评测范围与口径

- 固定公开 Gold 数据版本 `25ed67db7da8f4591484e764008ff585544f5a30`，Olympiad 100 题、Research 60 题。下载和准备阶段均校验预先固定的原始文件 SHA-256。
- 原样发送 `problem`（包括数据内置作答要求）；`answer` 只发给 judge。Research 的 `answer` 字段是评分细则。
- 使用 `track + row_index` 唯一标识，保留重复 task_group_id，不去重。
- Olympiad 判断答案等价；Research 0–10 分，>=7 算成功。分赛道、分学科报告，不混成一个总正确率。judge 分数与解释矛盾另记 audit_flags，绝不改写原始判分。
- **官方附录 B 提示词、替换为 Qwen judge、单次试验**。官方论文采用 GPT-5 high judge，附录 B 为官方提示词；v0.2.0按附录B转录提示词，排版规范化及角色封装假设见 docs/OFFICIAL_PROTOCOL.md；v0.1.0自定义JSON仅保留在旧归档。官方还进行了多次试验平均；本工具单次结果不能直接等同官方成绩。
- 同模型自评可能有偏差；单元测试和模拟接口测试只验证软件流程，不证明 judge 语义准确。正式成绩发布前需要人工抽查、校准与记录。
- 基础示例 solver max_tokens=16384，judge=4096，temperature=0，seed=17，thinking=false，并发1；judge 默认 strict_final。本次全量使用 examples/judge8192-mmlu.json：judge上限8192、mmlu_extract_first，其他参数相同。这些是本地配置，不是官方推荐值。

## 安装

在准备执行评测的容器中安装：

```bash
git clone https://github.com/vLLM-HUST/hust-eval-client-frontierscience.git
cd hust-eval-client-frontierscience
python3 -m venv --system-site-packages .venv
. .venv/bin/activate
python -m pip install --no-deps --no-build-isolation -e .
hust-eval-frontierscience --help
```

若独立环境没有 setuptools，先在该 venv 安装 `setuptools>=61`；不要改模型服务的 Python 环境。也可零安装使用 `PYTHONPATH=src python3 -m hust_eval_frontierscience`。

完整命令见 [操作手册](docs/QUICKSTART.md)。

| 命令 | 用途 |
|---|---|
| fetch / prepare | 下载固定数据；冻结数据、提示词、两角色配置、源码与可选 runtime contract |
| run / judge | 先答题、后评分，保存逐题完整请求、原始响应、usage、耗时和失败 |
| summary | 校验上下游对应关系，生成 summary.json、per_case.csv |
| materialize / bench | 生成不含答案的性能输入；调用 vllm bench serve 客户端 |
| hash-file / hash-model | 文件 SHA-256 / 模型目录哈希，可只算小文件 |
| contract / receipt | 记录预期配置，采集已有服务的实际 argv、日志与 effective 对照 |
| seal evidence / final / check | 冻结证据清单，将其与最终结果表 SHA-256 绑定并校验 |

## 完整性与失败处理

计划保存原始数据、tasks、两角色参数、评分提示词及客户端源码快照。执行前核对哈希。续跑仅允许相同计划和配置；已有成功或失败记录均保留，不自动重试。每题记录绑定计划和请求；judge 还绑定该题 solver 记录。文件原子落盘，输出目录有互斥锁。

solver 请求失败保留在分母并计失败；solver 达到长度上限仍交给 judge，但单独标注截断。默认 strict_final 要求正常结束且末行 VERDICT 有效；存在未完成评分时 success_rate=null，另报已确认成功比例下界。本次 mmlu_extract_first 会从截断输出提取首个完整、独立一行的 VERDICT；无效判定保留在全分母中计未成功，并单列无效、截断和复核标记。Research均分只计有效评分，不把缺失判分赋零分。两种口径不可混用。

`run --limit` 是冒烟测试，报告标注 subset_smoke。没有自动扩大为全量；全量需新输出目录。

答题/评分使用非流式 chat 请求，只记录端到端耗时，不伪造 TTFT。TTFT、TPOT、ITL、吞吐由独立 bench 提供。bench 使用服务端默认 chat template/thinking，可能不同于准确率配置；不声称两者 wire request 完全一致。压测应与答题、评分分时运行。

## 证据边界

预期 profile 不等于实际启动配置。`receipt` 需要操作者提供 actual argv 与 startup log，按字段输出 verified/log_only/argv_only/unverified/mismatch。客户端不能从 HTTP API 反推出全部启动参数；缺失就标缺失。`contract` 采集执行该命令所在环境的包版本，所以要在服务容器内执行。

SHA-256 能发现文件变化；不等于签名或可信时间戳。small-only 不验证完整权重。最终结果表由操作者制作，工具绑定 CSV/XLSX 等文件，不自动生成 Excel 工作簿。详见 [证据说明](docs/EVIDENCE.md)。

## 来源

- [官方数据](https://huggingface.co/datasets/openai/frontierscience/tree/25ed67db7da8f4591484e764008ff585544f5a30)
- [官方论文及附录](https://arxiv.org/abs/2601.21165)
- 哈希、receipt、配置核对和封存逻辑复用自同组织 `hust-eval-client-mmlu-pro`；已复制到此仓库独立维护，无运行时依赖。

## 开发验证

```bash
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

测试使用本机随机端口模拟服务和合成题目，不访问实际 vLLM，也不是正式成绩。v0.3.0 已完成真实160题作答、judge与独立bench；软件流程通过不代表judge语义校准通过。详见 [本次全量记录](docs/FULL_RUN_20261013.md)。

## 截断统计可选口径

使用 examples/judge8192-mmlu.json 可启用与历史 MMLU-Pro 相同的“截断仍提取、无效保留分母”原则。具体 VERDICT 提取规则、局限和新增统计见 [TRUNCATION_POLICY.md](docs/TRUNCATION_POLICY.md)。默认严格口径不变。
