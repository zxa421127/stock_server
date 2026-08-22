股票数据服务器自动化测试套件
================================

所有代码目录、Python文件和BAT文件均使用英文名称，避免Windows CMD编码、Python导入、压缩上传和自动部署出现中文路径兼容问题。
中文仅用于本说明、屏幕提示和测试报告。

安装位置：C:\stockdata\stock_server\e2e_tests
服务地址：必须显式设置 STOCK_TEST_BASE_URL；腾讯云测试实例通常为 http://127.0.0.1:8898
公网地址：请使用已配置HTTPS的测试域名，例如 https://test-api.example.com；不要开放8899端口

目录：
01_deployment             基础部署和Token保护测试
02_account_permissions    测试账户创建、账户状态和套餐权限矩阵
03_provider_catalog       数据来源注册及接口目录数量测试
04_all_data_interfaces    所有已注册数据来源、所有目录接口的严格真实数据测试
05_cache                  行情缓存测试

core                      内部测试代码，请勿单独移动或修改

全接口覆盖方式：
程序先调用 /api/v1/market/providers 获取服务器实际注册的数据来源；
再调用每个来源的 /catalog 获取实际接口清单；
最后逐个真实请求清单中的每一个接口。
接口数量以服务器运行时目录为准；Tushare、开盘啦和启用后的MiniQMT会逐项覆盖，后续Provider新增接口也会自动进入测试。

严格数据成功条件：HTTP 200、success=true、count>0、data非空。
报告保存每个成功接口的前3条真实返回数据作为佐证。

报告目录：由 STOCK_TEST_RESULT_DIR 指定；默认 data-test\auto_test_results
