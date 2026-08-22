# PATCH MANIFEST V3

基准：用户上传的 `stock_server(28).zip`。补丁保持项目根目录相对路径，解压覆盖即可。

| 相对路径 | 状态 | 字节数 | SHA-256 |
|---|---:|---:|---|
| `.env.example` | 修改 | 5140 | `f7b698bd7be673b5826edc63ded677fbf83baef4240e2186458e5475662a11ae` |
| `CHANGELOG.md` | 修改 | 2062 | `e3e8fd20b876b1885d5552f788bf7ef572613354467dfc4cdb42fa2087e567ec` |
| `REPLACE_INSTRUCTIONS_V3.md` | 新增 | 811 | `739f97ecad27fad35496ae7768d147c5c27534de4a9a0d3fd49cc56d6d304bd3` |
| `SOURCE_DIFF_V3.patch` | 新增（交付元数据） | 95214 | `8319f0c861ae7ec8263daf36438d5c1c609fd47e30e10b2f894e46cabd575814` |
| `check_feishu_bidding_schema.bat` | 新增 | 101 | `a32808cf645c90f3ee12a34244bfe8b61204fd17c4a59beb934c2a988e1d9994` |
| `config.py` | 修改 | 12858 | `b99e4a662d7e4afb63484b8a7b4b8ee5d8857eb0669b3651ed2060c3055194f3` |
| `docs/FEISHU_KAIPANLA_FIELD_MAPPING_V2.md` | 修改 | 6211 | `5e47d1718236ac44153311d0f7a5ea5a084bbc71c8897383184b914e2c59c5c4` |
| `docs/KAIPANLA_SNAPSHOT_DEPLOYMENT.md` | 修改 | 5229 | `b0a1870ed94123795e57b3a488a7f293e3dacc985ff065866672cd3130f7a08b` |
| `docs/RELEASE_SECURITY_CLEANUP.md` | 新增 | 1079 | `fabc46e0c77ed05a4a18b14725afcdabcc6e785879b6f644f5132761ed64185b` |
| `integrations/feishu/bitable.py` | 修改 | 19976 | `4509a247728ceddf0a2b34bad807bdf2dd8ba88aef043eb6d35478636196d148` |
| `routes/market_data_routes.py` | 修改 | 8067 | `7da01c20d0182b682240420b1dc65882ed60419f2a177f747a6a8ff165e180ba` |
| `services/feishu_sync_service.py` | 修改 | 33781 | `08911de2ea330d39aa5392416cb44b748201da3bd6d9a4305836e02477837966` |
| `services/kaipanla_bidding_service.py` | 修改 | 18979 | `da072283ab85ebde46f63fcb8cfe86d92cceedff57e4b12f99b08d8d783c2636` |
| `services/kaipanla_snapshot_repository.py` | 修改 | 12433 | `6356fd3767152b90a8ee8941f96b2e2fb1fe4d7ea5f0cbbdd4f00d82017b066b` |
| `services/kaipanla_snapshot_scheduler.py` | 修改 | 7672 | `7417cfc18fe22630118c6e78f138613e45707189f607dfdc7d95d2638d20ee20` |
| `tests/test_feishu_bidding_schema_tool.py` | 新增 | 910 | `8d3e8c9c5473a6dd6cdf0e838326fddef3fe1af31e27a10c12200569f7a31500` |
| `tests/test_feishu_bidding_schema_v2.py` | 新增 | 2108 | `ebade914d908fec9f8bd9f3f2716d13f218b4b205a51a613541368e48320325a` |
| `tests/test_feishu_bidding_sync_v2.py` | 新增 | 2369 | `05c9968227e752a7a7c0faa0ecf9bedb3c4779c9f335fb6e794218a0c0fc4fd0` |
| `tests/test_kaipanla_bidding_adapter.py` | 修改 | 3421 | `e107983e317acbbd889238fcf4a8a79b56a344204e6f980f5036988b7440d192` |
| `tests/test_kaipanla_bidding_service.py` | 修改 | 7606 | `267b23d3dd388357cc0d234242f3046372fd2609d018c002b52b674fec11a80f` |
| `tests/test_kaipanla_snapshot_scheduler.py` | 修改 | 4270 | `1c4a1409b0172dcc04212c85bfe1706e38c7bf3eddf88bddf71983d012569c4c` |
| `tests/test_kaipanla_v2_repository.py` | 修改 | 3638 | `99cf6019e3baf5505c22714e5f8a3965aace42ca33f83fce9904c89244c6122c` |
| `tests/test_kaipanla_v2_service.py` | 修改 | 4182 | `463c5145c4ef71bfc5a63d3dbf2aa157593077820c62f081fb35a0b7aec130ac` |
| `tools/check_feishu_bidding_schema.py` | 新增 | 1296 | `c1734d0a23306667d79d7a71a017e113900c942076e933856a45c634cae27ef0` |
| `测试结果_V3.md` | 新增（交付元数据） | 832 | `90ca2428c9d4962a983c4bff1c411986052b692dd4e03628da6f9f521ed103c7` |

- 修改文件：16 个
- 新增源码/测试/文档：7 个
- 交付元数据：2 个
