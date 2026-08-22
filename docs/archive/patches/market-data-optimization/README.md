股票数据平台：行情缓存、空数据测试与 stock_company 性能优化补丁
================================================================
适用源码：用户上传的 stock_server(23).zip
目录原则：运行入口与配置保留在项目根目录；维护工具统一放 tools/；
          测试放 tests/ 与 test_suite/；补丁说明、差异和校验文件放 docs/patches/。
修改原则：不改变现有 139 个接口数量，不改变正常接口 URL，不关闭生产缓存，
          不提高全局超时时间，不把实时行情放进缓存。


目录分类
--------
本补丁解压后，项目根目录只新增或覆盖运行必需文件：

```text
stock_server/
├── app.py                         # 应用入口，必须保留根目录
├── config.py                      # 全局配置，必须保留根目录
├── .env.example                   # 环境变量模板，必须保留根目录
├── services/                      # 生产服务代码
├── routes/                        # API 路由代码
├── integrations/                  # 数据源适配代码
├── tools/
│   ├── interface_tester.py        # 接口测试工具
│   └── market_data_optimization/  # 本补丁安装、整理、验证工具
├── tests/                         # 单元测试
├── test_suite/                    # 端到端测试
└── docs/patches/market_data_optimization/
    ├── README.md
    ├── PATCH_FILE_LIST.txt
    ├── SOURCE_DIFF.patch
    └── SHA256SUMS.txt
```

安装、验证、根目录整理脚本全部放在 `tools/market_data_optimization/`；
补丁说明、差异文件和校验文件全部放在 `docs/patches/market_data_optimization/`。
不会再向项目根目录加入工具脚本、补丁说明或校验清单。

一、本补丁解决的问题
--------------------
1. stock_company 返回 3083 条数据时，上游耗时从 1.23 秒恶化到 40 秒、60 秒超时。
2. 所有非实时接口共用 300 秒缓存，静态大数据接口重复访问上游。
3. 缓存过期后，慢接口会阻塞用户请求线程。
4. 上游临时失败或返回意外空数据时，已有正常缓存会失去兜底能力。
5. HTTP 200 空数据被统一算成“接口失败”，无法区分参数不匹配、历史停更和事件稀疏。
6. 全量测试可能读取缓存，无法证明真实上游状态。
7. etf_index、st、express、forecast 等接口的测试参数不够合理。

二、生产性能优化
----------------
1. 按接口设置缓存 TTL：
   - stock_company：86400 秒（24 小时）
   - stock_basic、财务报表等慢变化接口：21600 秒（6 小时）
   - trade_cal、bse_mapping：86400 秒
   - 其他普通接口：仍为 300 秒
   - 实时接口：继续完全排除缓存

2. 空结果只缓存 45 秒：
   避免临时空结果在网站上保留 5 分钟，同时防止用户不断击穿上游。

3. stale-if-error：
   仅对低频、静态、安全接口保留最近一次正常数据 7 天作为故障兜底。
   实时行情、资金流、日线等不会使用长期陈旧数据。

4. stale-while-revalidate：
   stock_company、stock_basic、trade_cal 接近过期或已过期时，
   用户立即获得缓存数据，最多 2 个后台线程负责刷新，不占用 Web 请求线程。

5. 防止坏刷新覆盖好缓存：
   上游刷新返回空数据或发生错误时，已有正常静态缓存不会被覆盖。

6. 可选后台预热：
   单进程 Waitress 部署可运行 tools\market_data_optimization\apply_market_data_optimization_env.bat，
   启动后后台预热 stock_company，不阻塞服务启动。
   多 worker Gunicorn 且没有共享 Redis 时，建议保持预热关闭。

三、测试准确性优化
------------------
1. 新增管理员专用无缓存验收地址：
   /api/v1/market/cache/query/<provider>/<api>
   必须具备 admin:sync 权限，普通会员不能使用。

2. 04_all_data_interfaces 测试默认通过该管理员地址强制访问真实上游：
   - 不读取生产缓存；
   - 成功结果仍写入缓存，不会让网站变冷；
   - 报告记录 cache_hit、cache_stale、upstream_elapsed_ms；
   - 503/no upstream available 做有限退避重试；
   - HTTP 200 空数据单独统计“接口可调用”。

3. 修正测试参数：
   - etf_index：不再错误传入 ETF 代码 510300.SH；先查询全量，备用指数代码 000300.SH。
   - st：不再传入正常股票 000001.SZ；先查询当前 ST 列表。
   - express、forecast：不再固定平安银行，优先按报告期/公告日期查询。
   - stk_holdertrade：优先查询市场事件，不固定无事件股票。
   - ccass_hold_detail：从 ccass_hold 成功结果动态选取代码和日期。
   - pledge_detail：改用更适合验证明细的样例代码，并保留备用参数。
   - 停更/历史接口：使用历史日期候选，不再用 2026 当前日期强制要求非空。

4. stock_company 验收测试只请求必要字段，避免测试本身因 3083 条宽表序列化而超时。
   正式网站接口的字段能力没有被删除，用户仍可自行传 fields。

四、接口目录补充信息
--------------------
Tushare 目录新增：
- lifecycle：active / historical
- test_note：历史接口验收说明

已标记历史口径：
- stk_account
- stk_account_old
- slb_len_mm
- slb_sec
- slb_sec_detail

接口总数仍为 138 个 Tushare + 1 个开盘啦 = 139 个。

五、替换步骤
------------
1. 停止服务：Ctrl+C
2. 备份当前项目目录。
3. 将本压缩包解压到 C:\stockdata\stock_server，覆盖同名文件。
   本补丁不包含 .env，不会覆盖 TUSHARE_TOKEN。
4. 若之前覆盖过上一版补丁，先运行：
   tools\market_data_optimization\organize_previous_patch_layout.bat
   它只会把上一版补丁遗留的6个根目录文件移动到 docs/patches 备份目录。
5. 建议单进程 Waitress 用户运行：
   tools\market_data_optimization\apply_market_data_optimization_env.bat
   脚本会先备份 .env，并且只更新 MARKET_DATA_* 配置。
6. 运行：
   tools\market_data_optimization\verify_market_data_optimization.bat
7. 重启：
   python app.py
8. 重新运行：
   C:\stockdata\stock_server\test_suite\04_all_data_interfaces\run.bat

六、回滚
--------
- 源码：用替换前备份恢复对应文件。
- .env：恢复脚本生成的 .env.before_market_data_optimization_时间戳 文件。

七、验证结果
------------
本次目录整理版已完成：
- Python 编译检查通过；
- 工具脚本从子目录定位项目根目录验证通过；
- 上一版根目录遗留文件整理工具验证通过；
- .env 安全更新工具验证通过，未改动 Token、数据库和会员配置；
- 压缩包根目录检查通过，仅包含 app.py、config.py、.env.example 三个运行必需文件。

当前隔离环境未安装 Flask 和 Tushare，因此本次未重新启动完整 Web 服务或重跑全部项目单元测试；
核心业务代码与上一版相同，只调整了工具和文档目录。替换后请在你的 .venv 中运行
`tools\market_data_optimization\verify_market_data_optimization.bat` 完成最终验收。
