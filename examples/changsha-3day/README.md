# changsha-3day

这个示例演示如何用 `scripts/tpf-pipeline.py` 从结构化输入一键生成旅行页面。

## 输入文件

- `input.json`：传给 `tpf-generate.py` 的结构化行程输入

## 运行方式

在仓库根目录执行：

```bash
python3 scripts/tpf-pipeline.py \
  --from-json examples/changsha-3day/input.json \
  --output-dir examples/changsha-3day/output \
  --pretty
```

如果你已经配置了 `TAVILY_API_KEY`，且不想自动搜索攻略，可以显式跳过：

```bash
python3 scripts/tpf-pipeline.py \
  --from-json examples/changsha-3day/input.json \
  --output-dir examples/changsha-3day/output \
  --skip-search \
  --pretty
```

## 生成结果

执行完成后，主要输出在：

- `examples/changsha-3day/output/data/trip-data.json`
- `examples/changsha-3day/output/dist/index.html`

如果启用了搜索步骤，还会额外生成：

- `examples/changsha-3day/output/data/travel-info.json`
