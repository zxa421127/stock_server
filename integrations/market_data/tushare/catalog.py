# -*- coding: utf-8 -*-
"""
integrations/market_data/tushare/catalog.py

Tushare 股票 / 指数 / ETF 接口白名单和别名表。

设计目的：
1. 不再为每个 Tushare 接口写一个单独 Python 文件。
2. 统一通过 /api/v1/market/tushare/<api_name> 调用。
3. 只允许股票、指数、ETF 相关接口，避免用户乱调用其它 Tushare 接口。
4. 用户可以用短横线形式访问，例如 stock-basic，会自动转成 stock_basic。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from integrations.market_data.tushare.permissions import (
    permission_class_for_api,
    permission_subtype_for_api,
    required_scope_for_api,
)


@dataclass(frozen=True)
class TushareApiMeta:
    api_name: str
    title: str
    category: str
    group: str
    realtime: bool = False
    note: str = ""
    lifecycle: str = "active"
    test_note: str = ""


# =========================
# 1. 股票类接口
# =========================
STOCK_APIS: Dict[str, TushareApiMeta] = {
    # 基础数据
    "stock_basic": TushareApiMeta("stock_basic", "股票列表", "股票类", "基础数据"),
    "stk_premarket": TushareApiMeta("stk_premarket", "每日股本（盘前）", "股票类", "基础数据"),
    "trade_cal": TushareApiMeta("trade_cal", "交易日历", "股票类", "基础数据"),
    "stock_st": TushareApiMeta("stock_st", "ST股票列表", "股票类", "基础数据"),
    "st": TushareApiMeta("st", "ST风险警示板股票", "股票类", "基础数据", note="旧路径 st_risk_warning 仍兼容。"),
    "stock_hsgt": TushareApiMeta("stock_hsgt", "沪深港通股票列表", "股票类", "基础数据"),
    "namechange": TushareApiMeta("namechange", "股票曾用名", "股票类", "基础数据"),
    "stock_company": TushareApiMeta(
        "stock_company",
        "上市公司基本信息",
        "股票类",
        "基础数据",
        note="大结果集、低频变化；服务端使用长缓存和后台刷新。",
    ),
    "stk_managers": TushareApiMeta("stk_managers", "上市公司管理层", "股票类", "基础数据"),
    "stk_rewards": TushareApiMeta("stk_rewards", "管理层薪酬和持股", "股票类", "基础数据"),
    "bse_mapping": TushareApiMeta("bse_mapping", "北交所新旧代码对照", "股票类", "基础数据"),
    "new_share": TushareApiMeta("new_share", "IPO新股上市", "股票类", "基础数据"),
    "bak_basic": TushareApiMeta("bak_basic", "股票历史列表", "股票类", "基础数据"),

    # 行情数据
    "daily": TushareApiMeta("daily", "历史日线", "股票类", "行情数据"),
    "weekly": TushareApiMeta("weekly", "周线行情", "股票类", "行情数据"),
    "monthly": TushareApiMeta("monthly", "月线行情", "股票类", "行情数据"),
    "adj_factor": TushareApiMeta("adj_factor", "复权因子", "股票类", "行情数据"),
    "daily_basic": TushareApiMeta("daily_basic", "每日指标", "股票类", "行情数据"),
    "pro_bar": TushareApiMeta("pro_bar", "通用行情接口", "股票类", "行情数据", note="SDK集成接口，内部走 ts.pro_bar。"),
    "stk_limit": TushareApiMeta("stk_limit", "每日涨跌停价格", "股票类", "行情数据"),
    "suspend_d": TushareApiMeta("suspend_d", "每日停复牌信息", "股票类", "行情数据"),
    "hsgt_top10": TushareApiMeta("hsgt_top10", "沪深股通十大成交股", "股票类", "行情数据"),
    "ggt_top10": TushareApiMeta("ggt_top10", "港股通十大成交股", "股票类", "行情数据"),
    "ggt_daily": TushareApiMeta("ggt_daily", "港股通每日成交统计", "股票类", "行情数据"),
    "bak_daily": TushareApiMeta("bak_daily", "备用行情", "股票类", "行情数据"),
    "stk_mins": TushareApiMeta("stk_mins", "历史分钟", "股票类", "行情数据", note="中转服务可能需要单独开通分钟接口权限。"),
    "rt_k": TushareApiMeta("rt_k", "实时日线", "股票类", "行情数据", realtime=True),
    "rt_min": TushareApiMeta("rt_min", "实时分钟", "股票类", "行情数据", realtime=True),
    "rt_min_daily": TushareApiMeta("rt_min_daily", "A股实时分钟-日累计", "股票类", "行情数据", realtime=True),

    # 财务数据
    "income": TushareApiMeta("income", "利润表", "股票类", "财务数据"),
    "balancesheet": TushareApiMeta("balancesheet", "资产负债表", "股票类", "财务数据"),
    "cashflow": TushareApiMeta("cashflow", "现金流量表", "股票类", "财务数据"),
    "forecast": TushareApiMeta("forecast", "业绩预告", "股票类", "财务数据"),
    "express": TushareApiMeta("express", "业绩快报", "股票类", "财务数据"),
    "dividend": TushareApiMeta("dividend", "分红送股数据", "股票类", "财务数据"),
    "fina_indicator": TushareApiMeta("fina_indicator", "财务指标数据", "股票类", "财务数据"),
    "fina_audit": TushareApiMeta("fina_audit", "财务审计意见", "股票类", "财务数据"),
    "fina_mainbz": TushareApiMeta("fina_mainbz", "主营业务构成", "股票类", "财务数据"),
    "disclosure_date": TushareApiMeta("disclosure_date", "财报披露日期表", "股票类", "财务数据"),

    # 参考数据
    "stk_shock": TushareApiMeta("stk_shock", "个股异常波动", "股票类", "参考数据", note="旧路径 stk_surv 仍兼容。"),
    "stk_high_shock": TushareApiMeta("stk_high_shock", "个股严重异常波动", "股票类", "参考数据", note="旧路径 stk_surv_detail 仍兼容。"),
    "stk_alert": TushareApiMeta("stk_alert", "交易所重点提示证券", "股票类", "参考数据", note="旧路径 stk_warn 仍兼容。"),
    "top10_holders": TushareApiMeta("top10_holders", "前十大股东", "股票类", "参考数据"),
    "top10_floatholders": TushareApiMeta("top10_floatholders", "前十大流通股东", "股票类", "参考数据"),
    "pledge_stat": TushareApiMeta("pledge_stat", "股权质押统计数据", "股票类", "参考数据"),
    "pledge_detail": TushareApiMeta("pledge_detail", "股权质押明细数据", "股票类", "参考数据"),
    "repurchase": TushareApiMeta("repurchase", "股票回购", "股票类", "参考数据"),
    "share_float": TushareApiMeta("share_float", "限售股解禁", "股票类", "参考数据"),
    "block_trade": TushareApiMeta("block_trade", "大宗交易", "股票类", "参考数据"),
    "stk_account": TushareApiMeta(
        "stk_account",
        "股票开户数据",
        "股票类",
        "参考数据",
        lifecycle="historical",
        test_note="历史/停更接口，应使用历史日期验收，不参与当前日期非空率。",
    ),
    "stk_account_old": TushareApiMeta(
        "stk_account_old",
        "股票开户数据（旧）",
        "股票类",
        "参考数据",
        note="历史接口；当前中转服务可能不支持，官方模式保留。",
        lifecycle="historical",
        test_note="仅使用历史区间测试；中转不支持时从默认可用目录降级。",
    ),
    "stk_holdernumber": TushareApiMeta("stk_holdernumber", "股东人数", "股票类", "参考数据"),
    "stk_holdertrade": TushareApiMeta("stk_holdertrade", "股东增减持", "股票类", "参考数据"),

    # 特色数据
    "report_rc": TushareApiMeta("report_rc", "券商盈利预测数据", "股票类", "特色数据"),
    "cyq_perf": TushareApiMeta("cyq_perf", "每日筹码及胜率", "股票类", "特色数据"),
    "cyq_chips": TushareApiMeta("cyq_chips", "每日筹码分布", "股票类", "特色数据"),
    "stk_factor": TushareApiMeta("stk_factor", "股票技术面因子", "股票类", "特色数据"),
    "stk_factor_pro": TushareApiMeta("stk_factor_pro", "股票技术面因子专业版", "股票类", "特色数据"),
    "ccass_hold": TushareApiMeta("ccass_hold", "中央结算系统持股统计", "股票类", "特色数据"),
    "ccass_hold_detail": TushareApiMeta("ccass_hold_detail", "中央结算系统持股明细", "股票类", "特色数据"),
    "hk_hold": TushareApiMeta("hk_hold", "沪深港股通持股明细", "股票类", "特色数据", note="旧路径 hsgt_hold_stock 仍兼容。"),
    "stk_auction_o": TushareApiMeta("stk_auction_o", "股票开盘集合竞价数据", "股票类", "特色数据"),
    "stk_auction_c": TushareApiMeta("stk_auction_c", "股票收盘集合竞价数据", "股票类", "特色数据"),
    "stk_nineturn": TushareApiMeta("stk_nineturn", "神奇九转指标", "股票类", "特色数据"),
    "stk_ah_comparison": TushareApiMeta("stk_ah_comparison", "AH股比价", "股票类", "特色数据"),
    "irm_qa_sh": TushareApiMeta("irm_qa_sh", "上证e互动问答", "股票类", "特色数据"),
    "irm_qa_sz": TushareApiMeta("irm_qa_sz", "深证易互动问答", "股票类", "特色数据"),
    "broker_recommend": TushareApiMeta("broker_recommend", "券商月度金股", "股票类", "特色数据"),

    # 两融及转融通
    "margin": TushareApiMeta("margin", "融资融券交易汇总", "股票类", "两融及转融通"),
    "margin_detail": TushareApiMeta("margin_detail", "融资融券交易明细", "股票类", "两融及转融通"),
    "margin_secs": TushareApiMeta("margin_secs", "融资融券标的", "股票类", "两融及转融通"),
    "slb_len": TushareApiMeta("slb_len", "转融券交易汇总", "股票类", "两融及转融通"),
    "slb_sec": TushareApiMeta(
        "slb_sec",
        "转融资交易汇总",
        "股票类",
        "两融及转融通",
        lifecycle="historical",
        test_note="历史/停更口径，使用历史日期验收。",
    ),
    "slb_len_mm": TushareApiMeta(
        "slb_len_mm",
        "转融券交易明细",
        "股票类",
        "两融及转融通",
        lifecycle="historical",
        test_note="历史/停更口径，使用历史日期验收。",
    ),
    "slb_sec_detail": TushareApiMeta(
        "slb_sec_detail",
        "做市借券交易汇总",
        "股票类",
        "两融及转融通",
        lifecycle="historical",
        test_note="历史/停更口径，使用历史日期验收。",
    ),

    # 资金流向数据
    "moneyflow": TushareApiMeta("moneyflow", "个股资金流向", "股票类", "资金流向"),
    "moneyflow_ths": TushareApiMeta("moneyflow_ths", "个股资金流向（THS）", "股票类", "资金流向"),
    "moneyflow_dc": TushareApiMeta("moneyflow_dc", "个股资金流向（DC）", "股票类", "资金流向"),
    "moneyflow_ind_ths": TushareApiMeta("moneyflow_ind_ths", "行业资金流向（THS）", "股票类", "资金流向"),
    "moneyflow_ind_dc": TushareApiMeta("moneyflow_ind_dc", "板块资金流向（DC）", "股票类", "资金流向"),
    "moneyflow_mkt_dc": TushareApiMeta("moneyflow_mkt_dc", "大盘资金流向（DC）", "股票类", "资金流向"),
    "moneyflow_hsgt": TushareApiMeta("moneyflow_hsgt", "沪深港通资金流向", "股票类", "资金流向"),

    # 打板专题数据
    "top_list": TushareApiMeta("top_list", "龙虎榜每日统计单", "股票类", "打板专题"),
    "top_inst": TushareApiMeta("top_inst", "龙虎榜机构交易单", "股票类", "打板专题"),
    "limit_list_ths": TushareApiMeta("limit_list_ths", "涨跌停榜单（同花顺）", "股票类", "打板专题", note="旧路径 ths_limit 仍兼容。"),
    "limit_list_d": TushareApiMeta("limit_list_d", "涨跌停和炸板数据", "股票类", "打板专题", note="旧路径 limit_list 仍兼容。"),
    "limit_step": TushareApiMeta("limit_step", "涨停股票连板天梯", "股票类", "打板专题"),
    "limit_cpt_list": TushareApiMeta("limit_cpt_list", "涨停最强板块统计", "股票类", "打板专题"),
    "ths_index": TushareApiMeta("ths_index", "THS概念板块分类", "股票类", "打板专题"),
    "ths_daily": TushareApiMeta("ths_daily", "THS概念板块行情", "股票类", "打板专题"),
    "ths_member": TushareApiMeta("ths_member", "THS概念板块成分", "股票类", "打板专题"),
    "dc_index": TushareApiMeta("dc_index", "DC概念板块分类", "股票类", "打板专题"),
    "dc_member": TushareApiMeta("dc_member", "DC概念板块成分", "股票类", "打板专题"),
    "dc_daily": TushareApiMeta("dc_daily", "DC概念板块行情", "股票类", "打板专题"),
    "hm_list": TushareApiMeta("hm_list", "市场游资最全名录", "股票类", "打板专题"),
    "hm_detail": TushareApiMeta("hm_detail", "游资交易每日明细", "股票类", "打板专题"),
    "ths_hot": TushareApiMeta("ths_hot", "THS热榜", "股票类", "打板专题"),
    "dc_hot": TushareApiMeta("dc_hot", "DC热榜", "股票类", "打板专题"),
    "tdx_index": TushareApiMeta("tdx_index", "TDX概念板块分类", "股票类", "打板专题"),
    "tdx_member": TushareApiMeta("tdx_member", "TDX概念板块成分", "股票类", "打板专题"),
    "tdx_daily": TushareApiMeta("tdx_daily", "TDX概念板块行情", "股票类", "打板专题"),
    "kpl_list": TushareApiMeta("kpl_list", "榜单数据（KP）", "股票类", "打板专题"),
    "kpl_concept_cons": TushareApiMeta("kpl_concept_cons", "开盘啦题材成分", "股票类", "打板专题", note="旧路径 kpl_concept 仍兼容。"),
    "dc_concept": TushareApiMeta("dc_concept", "题材库", "股票类", "打板专题", note="旧路径 dc_thematic 仍兼容。"),
    "dc_concept_cons": TushareApiMeta("dc_concept_cons", "题材成分", "股票类", "打板专题", note="旧路径 dc_thematic_detail 仍兼容。"),
}


# =========================
# 2. ETF 类接口
# =========================
ETF_APIS: Dict[str, TushareApiMeta] = {
    "etf_basic": TushareApiMeta("etf_basic", "ETF基本信息", "ETF类", "ETF专题"),
    "etf_index": TushareApiMeta("etf_index", "ETF跟踪指数", "ETF类", "ETF专题"),
    "rt_etf_min": TushareApiMeta("rt_etf_min", "ETF实时分钟", "ETF类", "ETF专题", realtime=True),
    "rt_etf_min_daily": TushareApiMeta("rt_etf_min_daily", "ETF实时分钟-日累计", "ETF类", "ETF专题", realtime=True),
    "etf_mins": TushareApiMeta("etf_mins", "ETF历史分钟", "ETF类", "ETF专题", note="中转服务可能需要单独开通分钟接口权限。"),
    "rt_etf_k": TushareApiMeta("rt_etf_k", "ETF实时日线", "ETF类", "ETF专题", realtime=True),
    "fund_daily": TushareApiMeta("fund_daily", "ETF日线行情", "ETF类", "ETF专题"),
    "fund_adj": TushareApiMeta("fund_adj", "ETF复权因子", "ETF类", "ETF专题"),
    "etf_share_size": TushareApiMeta("etf_share_size", "ETF份额规模", "ETF类", "ETF专题"),
    "etf_sh_cons": TushareApiMeta("etf_sh_cons", "ETF每日持仓组合（沪市）", "ETF类", "ETF专题", note="旧路径 etf_pcf 仍兼容。"),
    "etf_sz_cons": TushareApiMeta("etf_sz_cons", "ETF每日持仓组合（深市）", "ETF类", "ETF专题", note="旧路径 etf_pcf_sz 仍兼容。"),
    "rt_etf_sz_iopv": TushareApiMeta("rt_etf_sz_iopv", "ETF实时参考", "ETF类", "ETF专题", realtime=True, note="旧路径 etf_ref 仍兼容；官网当前仅提供深市。"),
    "idx_anns": TushareApiMeta("idx_anns", "指数公告", "ETF类", "ETF专题", note="旧路径 index_ann 仍兼容。"),
}


# =========================
# 3. 指数类接口
# =========================
INDEX_APIS: Dict[str, TushareApiMeta] = {
    "index_basic": TushareApiMeta("index_basic", "指数基本信息", "指数类", "指数专题"),
    "index_daily": TushareApiMeta("index_daily", "指数日线行情", "指数类", "指数专题"),
    "rt_idx_k": TushareApiMeta("rt_idx_k", "交易所指数实时日线", "指数类", "指数专题", realtime=True, note="旧路径 rt_index_k 仍兼容。"),
    "rt_idx_min": TushareApiMeta("rt_idx_min", "指数实时分钟", "指数类", "指数专题", realtime=True, note="旧路径 rt_index_min 仍兼容。"),
    "index_weekly": TushareApiMeta("index_weekly", "指数周线行情", "指数类", "指数专题"),
    "idx_mins": TushareApiMeta("idx_mins", "指数历史分钟", "指数类", "指数专题", note="旧路径 index_mins 仍兼容；中转服务可能需要单独开通分钟接口权限。"),
    "index_monthly": TushareApiMeta("index_monthly", "指数月线行情", "指数类", "指数专题"),
    "index_weight": TushareApiMeta("index_weight", "指数成分和权重", "指数类", "指数专题"),
    "index_dailybasic": TushareApiMeta("index_dailybasic", "大盘指数每日指标", "指数类", "指数专题"),
    "index_classify": TushareApiMeta("index_classify", "申万行业分类", "指数类", "指数专题"),
    "index_member_all": TushareApiMeta("index_member_all", "申万行业成分构成（分级）", "指数类", "指数专题", note="旧路径 index_member 仍兼容；参数改为 l1_code/l2_code/l3_code/ts_code。"),
    "sw_daily": TushareApiMeta("sw_daily", "申万日线行情", "指数类", "指数专题"),
    "rt_sw_k": TushareApiMeta("rt_sw_k", "申万实时行情", "指数类", "指数专题", realtime=True, note="旧路径 sw_realtime 仍兼容。"),
    "sw_mins": TushareApiMeta("sw_mins", "SW历史分钟", "指数类", "指数专题", note="旧路径 sw_min 仍兼容；中转服务可能需要单独开通分钟接口权限。"),
    "ci_index_member": TushareApiMeta("ci_index_member", "中信行业成分", "指数类", "指数专题"),
    "ci_daily": TushareApiMeta("ci_daily", "中信行业指数日行情", "指数类", "指数专题"),
    "index_global": TushareApiMeta("index_global", "国际主要指数", "指数类", "指数专题", note="旧路径 global_index 仍兼容。"),
    "idx_factor_pro": TushareApiMeta("idx_factor_pro", "指数技术面因子专业版", "指数类", "指数专题", note="旧路径 index_factor_pro 仍兼容。"),
    "daily_info": TushareApiMeta("daily_info", "市场交易统计", "指数类", "指数专题", note="旧路径 index_market 仍兼容。"),
    "sz_daily_info": TushareApiMeta("sz_daily_info", "深圳市场每日交易情况", "指数类", "指数专题"),
}


TUSHARE_API_CATALOG: Dict[str, TushareApiMeta] = {}
TUSHARE_API_CATALOG.update(STOCK_APIS)
TUSHARE_API_CATALOG.update(ETF_APIS)
TUSHARE_API_CATALOG.update(INDEX_APIS)


# 对外 URL 书写别名：仅用于短横线/下划线等路径写法归一化。
TUSHARE_API_ALIASES = {
    "stock-basic": "stock_basic",
    "stock_basic": "stock_basic",
    "trade-calendar": "trade_cal",
    "trade_cal": "trade_cal",
    "name-change": "namechange",
    "name_change": "namechange",
    "daily-basic": "daily_basic",
    "daily_basic": "daily_basic",
    "adj-factor": "adj_factor",
    "adj_factor": "adj_factor",
    "stock-hsgt": "stock_hsgt",
    "st-risk-warning": "st",
    "stock-company": "stock_company",
    "stk-managers": "stk_managers",
    "stk-rewards": "stk_rewards",
    "bse-mapping": "bse_mapping",
    "new-share": "new_share",
    "bak-basic": "bak_basic",
    "index-daily": "index_daily",
    "index-basic": "index_basic",
    "index-weight": "index_weight",
    "etf-basic": "etf_basic",
    "etf-index": "etf_index",
    "etf-daily": "fund_daily",
    "etf-adj": "fund_adj",
    "etf-mins": "etf_mins",
    "fund-daily": "fund_daily",
    "fund-adj": "fund_adj",

    # 官网接口名迁移兼容：目录只展示官网真实名称，旧路径仍可调用。
    "st_risk_warning": "st",
    "stk_surv": "stk_shock",
    "stk_surv_detail": "stk_high_shock",
    "stk_warn": "stk_alert",
    "hsgt_hold_stock": "hk_hold",
    "ths_limit": "limit_list_ths",
    "limit_list": "limit_list_d",
    "kpl_concept": "kpl_concept_cons",
    "dc_thematic": "dc_concept",
    "dc_thematic_detail": "dc_concept_cons",
    "etf_pcf": "etf_sh_cons",
    "etf_pcf_sz": "etf_sz_cons",
    "etf_ref": "rt_etf_sz_iopv",
    "index_ann": "idx_anns",
    "rt_index_k": "rt_idx_k",
    "rt_index_min": "rt_idx_min",
    "index_member": "index_member_all",
    "sw_realtime": "rt_sw_k",
    "index_market": "daily_info",

    # 官方接口更名兼容：目录展示当前名称，旧路径继续可用。
    "global_index": "index_global",
    "global-index": "index_global",
    "index_mins": "idx_mins",
    "index-mins": "idx_mins",
    "index_factor_pro": "idx_factor_pro",
    "index-factor-pro": "idx_factor_pro",
    "sw_min": "sw_mins",
    "sw-min": "sw_mins",
}


def normalize_api_name(raw_name: str) -> str:
    name = (raw_name or "").strip()
    name = name.strip("/")
    if not name:
        return ""
    lower = name.lower()
    if lower in TUSHARE_API_ALIASES:
        return TUSHARE_API_ALIASES[lower]
    return lower.replace("-", "_")


def get_api_meta(api_name: str) -> Optional[TushareApiMeta]:
    return TUSHARE_API_CATALOG.get(normalize_api_name(api_name))


def is_allowed_tushare_api(api_name: str) -> bool:
    return normalize_api_name(api_name) in TUSHARE_API_CATALOG


def list_tushare_apis() -> List[dict]:
    rows = []
    for meta in TUSHARE_API_CATALOG.values():
        rows.append({
            "api_name": meta.api_name,
            "title": meta.title,
            "category": meta.category,
            "group": meta.group,
            "realtime": meta.realtime,
            "note": meta.note,
            "lifecycle": meta.lifecycle,
            "test_note": meta.test_note,
            "permission_class": permission_class_for_api(meta.api_name),
            "permission_subtype": permission_subtype_for_api(meta.api_name),
            "required_scope": required_scope_for_api(meta.api_name),
            "url": f"/api/v1/market/tushare/{meta.api_name}",
        })
    return sorted(rows, key=lambda x: (x["category"], x["group"], x["api_name"]))
