# 一键数据接口测试工具

## 安装

把压缩包中的文件复制到 `stock_server` 根目录：

```text
stock_server/
├── scripts/windows/run_interface_test.bat
└── tools/
    └── interface_tester.py
```

不会覆盖业务代码。

## 使用

1. 在一个命令窗口运行：

```bash
python run_waitress.py
```

2. 双击：

```text
scripts/windows/run_interface_test.bat
```

3. 首次输入一次 `X-API-Token`。可以选择保存在本机：

```text
data/interface_test_token.txt
```

该文件已位于 `.gitignore` 忽略的 `data/` 目录，不会进入代码包。

4. 按菜单选择：

- 测一条接口；
- 测多条接口；
- 测某个数据源全部接口；
- 测全部数据接口；
- 查看接口目录与数据源健康状态。

示例接口名：

```text
daily
tushare.daily
kaipanla.morning_bidding
miniqmt.quote
```

## 测试结果

报告自动保存到：

```text
data/interface_test_results/
├── interface_test_时间.csv
└── interface_test_时间.json
```

结果含义：

- `有数据`：HTTP成功且返回条数大于0；
- `成功但为空`：接口可调用，但当前参数/日期没有数据；
- `套餐无权限`：stock_server套餐权限不足；
- `上游无权限`：Tushare积分或独立接口权限不足；
- `上游调用失败`：Tushare/开盘啦/MiniQMT返回错误；
- `触发限流`：达到分钟、每日或全局额度；
- `数据源不可用`：配置缺失或客户端没有启动。

## 注意

“测试全部接口”会真实调用上游数据源，可能消耗Tushare额度。不同接口需要不同积分或独立权限，因此全量结果中出现“上游无权限”不等于本地服务器代码有问题。
