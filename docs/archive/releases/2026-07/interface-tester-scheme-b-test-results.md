# 市场接口测试台方案B测试结果

测试日期：2026-07-25

## 1. 核心功能回归

执行：

```text
pytest tests/test_tushare_spec_sync_service.py
       tests/test_sync_tushare_interface_specs_cli.py
       tests/test_market_interface_specs.py
       tests/test_admin_market_test_routes.py
       tests/test_admin_market_test_service.py
       tests/test_admin_api_test_batch_service.py
       tests/test_admin_api_test_repository.py
       tests/test_admin_api_test_cleanup_service.py
       tests/test_interface_test_params.py
       tests/test_interface_spec_audit_tool.py
       tests/test_api_doc_service.py -q
```

结果：

```text
78 passed
```

覆盖内容包括：

- 官方 Markdown/HTML 解析；
- TuShare 实际无外层竖线 Markdown 表格格式；
- ETF 6 输入、14 输出及顺序；
- 官网同步候选、差异、失败隔离和发布门禁；
- 分类筛选和目录计数；
- 前后端拒绝用户输出字段选择；
- TuShare 请求自动使用全部输出字段；
- 批量、重试和验证任务固定全字段；
- 默认保留天数持久化及范围校验；
- 批次保留、清理和工作线程竞态；
- API 文档积分 Scope 统计兼容；
- 规格审计工具和同步 CLI 退出码。

## 2. 扩大回归

在排除当前 Linux 沙箱无法导入的飞书/压缩可选原生依赖测试后执行其余测试：

```text
337 passed, 82 subtests passed
```

被排除测试的原因不是本次代码失败：上传源码中的 `.venv` 为 Windows 环境，当前 Linux 沙箱缺少可用的 `backports.zstd` 原生模块和 `Crypto` 模块，导致相关测试在收集或动态导入阶段失败。

## 3. 静态检查

```text
python -m compileall -q config.py routes services tools tests
node --check <从 templates/admin/interface_tester.html 提取的脚本>
```

结果：通过。

## 4. 当前活动规格验证

```text
版本：spec-20260725-official-bootstrap-v1
接口总数：140
Provider：TuShare 138，开盘啦 2
业务类目：12
ETF输入：6
ETF输出：14
禁止 fields 输入的接口数：0
```

## 5. 当前审计状态与联网限制

当前启动规格中：

```text
official_verified = 3
tushare_pending_official = 137
incomplete = 18
missing_output_count = 18
```

这不是把未完成接口判为成功。沙箱 DNS 无法访问 TuShare/GitHub，因而不能在打包环境完成 137 个官网页面的真实抓取。全量同步代码已经通过官方格式夹具和模拟网络成功/失败场景验证；部署到可联网服务器后，必须取得 `138/138、complete_sync=true`，经管理员审核发布后再进行全量真实上游测试。
