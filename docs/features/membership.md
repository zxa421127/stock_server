# 一键会员权限测试

把压缩包内容复制到 `C:\stockdata\stock_server`，不会覆盖业务代码，只新增：

- `scripts/windows/run_membership_test.bat`
- `tools/membership_tester.py`

使用方法：

1. 保持 `python run_waitress.py` 正在运行；
2. 双击 `scripts/windows/run_membership_test.bat`；
3. 查看“通过/失败”结果。

脚本使用当前正式路径 `/api/v1/market/...`，不会使用已删除的 `/api/data/...` 或 `/api/v1/tushare/...`。

它会创建专用测试用户，验证：

- 无 Token：401；
- 错误或禁用 Token：401；
- 未开通或过期套餐：402；
- 历史会员访问 Tushare：200；
- 历史会员访问开盘啦：403；
- 实时会员访问开盘啦：200；
- 实时会员访问管理员缓存接口：403；
- 管理员访问管理员缓存接口：200。

真实 Tushare/开盘啦上游测试单独显示，不计入会员权限测试总分。
