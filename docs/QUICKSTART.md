# 远程操作手册

以下均在远程容器执行。先安装 README 所述客户端，确认已有服务可用。不要照抄启动参数来冒充实际启动证据。

## 1. 数据和配置

```bash
cd /root/hust-eval-client-frontierscience
. .venv/bin/activate
hust-eval-frontierscience fetch --output data/frontierscience
mkdir -p runs/fs-smoke
cp examples/solver.json runs/fs-smoke/solver.json
cp examples/judge.json runs/fs-smoke/judge.json
```

复现2026-10-13全量时，将 examples/judge8192-mmlu.json 复制为本次 judge.json，明确选择8192上限与 mmlu_extract_first。基础 judge.json 保持4096和严格评分。必须在prepare前选择，不可事后更换冻结计划。

若数据已在该目录且已校验，跳过 fetch；离线也可复制固定版本的 `olympiad/test.jsonl` 和 `research/test.jsonl` 到该目录，prepare 会检查内置 hash。fetch 下载失败可能留下部分目录；保留用于诊断，下次下载换新目录。

编辑两个 JSON：URL、served model、model_artifact、请求参数与并发。示例均为现有 Qwen3.5-35B-A3B、端口18180。配置中的模型路径只是身份记录，客户端不加载权重。base_url 可以带或不带 `/v1`，prepare 会规范化。若启用鉴权，设 `api_key_env` 为环境变量名，在 shell 导出实际密钥。

准备计划之后不要改客户端源码或配置；需要变更时重新 prepare，并创建新运行目录。

## 2. 服务证据

先按真实运行环境修订 expected profile；示例 env 的设备号只是示例，须与实际一致。由操作者在服务容器提供 actual argv JSON 数组和启动日志快照。例如保存到 `/root/server-evidence/argv.json`、`startup.log`；它们必须来自实际服务，不能用 expected profile 生成。

```bash
mkdir -p runs/fs-smoke/model
hust-eval-frontierscience hash-model --model /models/Qwen3.5-35B-A3B \
  --small-only --out runs/fs-smoke/model/small-hashes.json
hust-eval-frontierscience contract --profile examples/profile.b0_35b.json \
  --out runs/fs-smoke/solver-runtime.json
hust-eval-frontierscience receipt --run-dir runs/fs-smoke/solver-service \
  --base-url http://127.0.0.1:18180 --profile examples/profile.b0_35b.json \
  --server-argv /root/server-evidence/argv.json --startup-log /root/server-evidence/startup.log
```

没有日志/argv 时可省略相应选项，报告会显示证据不足。镜像 digest 已知时用 `--image-id`；未知保留 NOT_PROVIDED。同服务充当 judge 时，在开始 judge 阶段前对 `runs/fs-smoke/judge-service` 再采一次 receipt。不同服务应各自提供 profile、模型工件和 startup 证据。

## 3. 冻结、小样本答题、评分

```bash
hust-eval-frontierscience prepare --assets data/frontierscience \
  --solver-config runs/fs-smoke/solver.json --judge-config runs/fs-smoke/judge.json \
  --solver-runtime-contract runs/fs-smoke/solver-runtime.json \
  --output runs/fs-smoke/plan
hust-eval-frontierscience run --plan runs/fs-smoke/plan \
  --output runs/fs-smoke/solver --limit 3
hust-eval-frontierscience judge --plan runs/fs-smoke/plan \
  --responses runs/fs-smoke/solver --output runs/fs-smoke/judge
hust-eval-frontierscience summary --plan runs/fs-smoke/plan \
  --responses runs/fs-smoke/solver --grades runs/fs-smoke/judge \
  --output runs/fs-smoke/report
```

这里前三题只覆盖 Olympiad。全量前还要抽 Research 验证长回答与 rubric 评分（可使用 `run --track research --limit 3`，单独输出目录）。检查 raw_response、finish_reason、judge reason、audit_flags、错误和截断；人工确认 judge 可用。限制只作用于客户端任务选择，不改全量计划。

如果进程中断，原命令加 `--resume`；不重试已经落盘的失败，保证口径不悄悄变化。若进程被强杀留下 `.active.lock`，确认原进程已退出后手动移除锁再续跑。不要在同一目录同时启动两个客户端。

## 4. 全量与 bench

参数确定后创建 `runs/fs-full`，重复配置、证据和 prepare 步骤。全量 run 不带 `--limit`：

```bash
hust-eval-frontierscience run --plan runs/fs-full/plan --output runs/fs-full/solver
hust-eval-frontierscience judge --plan runs/fs-full/plan \
  --responses runs/fs-full/solver --output runs/fs-full/judge
hust-eval-frontierscience summary --plan runs/fs-full/plan \
  --responses runs/fs-full/solver --grades runs/fs-full/judge --output runs/fs-full/report
hust-eval-frontierscience materialize --plan runs/fs-full/plan --output runs/fs-full/bench-prompts.jsonl
hust-eval-frontierscience bench --run-dir runs/fs-full/bench --name frontierscience \
  --dataset runs/fs-full/bench-prompts.jsonl --base-url http://127.0.0.1:18180 \
  --served-model qwen3.5-35b --tokenizer /models/Qwen3.5-35B-A3B \
  --num-prompts 160 --output-len 256 --dry-run
```

bench 需要客户端环境可执行 `vllm bench serve`，可以用 `--vllm-bin /绝对路径/vllm`。dry-run 核对命令后，实际执行请换新的 `--run-dir`（例如 `runs/fs-full/bench-live`），去掉 `--dry-run`。固定 inf 到达率、temperature0、seed0；服务端请求长度限制等由实际配置决定。鉴权服务可按 vLLM 客户端要求在外部配置密钥，不写入命令或仓库。

## 5. 表格与封存

结束请求并收集所有静态证据后：

```bash
hust-eval-frontierscience seal evidence --run-dir runs/fs-full
```

将输出的 evidence_bundle_sha256 写入最终表格的 Provenance 页（CSV 可作为列或随附描述）。表格放在 `runs/fs-full/results/` 下，这个目录不参与第一阶段证据哈希，避免循环依赖。结果表制作完毕后：

```bash
hust-eval-frontierscience seal final --run-dir runs/fs-full \
  --table runs/fs-full/results/frontierscience.xlsx --ledger runs/seal-ledger.jsonl
hust-eval-frontierscience seal check --run-dir runs/fs-full \
  --table runs/fs-full/results/frontierscience.xlsx
```

seal final 不会替你创建表格。MANIFEST.json 绑定证据 hash 与表格 hash；把 manifest hash 留到仓库提交或外部记录中。封存后不要再往运行目录写文件。
