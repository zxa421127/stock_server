# internal_error / 下载404补丁测试结果

测试日期：2026-07-25

## 定向回归

```text
31 passed
```

覆盖：

- Windows只读句柄 `fsync` 兼容性模拟；
- 空结果表头CSV；
- 上游错误结果归档；
- 存储异常分类；
- 未处理转换异常诊断文件；
- 下载409/410语义；
- 页面按文件路径条件展示链接；
- 原有批次、保留策略、接口规格和路由行为。

## 扩大回归

```text
343 passed, 82 subtests passed
```

完整测试收集受当前沙箱缺少 `pycryptodome` 和 `backports.zstd` 二进制依赖影响；受影响的是飞书和应用压缩相关测试，不涉及本次接口测试存储链路。排除这些环境依赖测试后，其余回归全部通过。

## 静态检查

- Python `compileall`：通过；
- `interface_tester.html` 内嵌 JavaScript `node --check`：通过。
