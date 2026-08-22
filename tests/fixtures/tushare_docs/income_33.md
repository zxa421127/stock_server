## 利润表
接口：income
描述：获取上市公司财务利润表数据
积分：用户需要至少2000积分才可以调取

**输入参数**
| 名称 | 类型 | 必选 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | 股票代码 |
| ann_date | str | N | 公告日期 |
| period | str | N | 报告期 |

**输出参数**
| 名称 | 类型 | 默认显示 | 描述 |
| --- | --- | --- | --- |
| ts_code | str | Y | TS代码 |
| ann_date | str | Y | 公告日期 |
| revenue | float | Y | 营业收入 |
| total_cogs | float | Y | 营业总成本 |
| n_income | float | Y | 净利润 |
| update_flag | str | Y | 更新标识 |
