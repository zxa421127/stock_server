# -*- coding: utf-8 -*-
"""
token_generator.py

单 Token 版本会员开通工具：
- 只生成/返回 users + api_keys + subscriptions + plans 这套新会员 Token。
- 不再写入旧 api_tokens 表。
- 用户请求头仍然统一使用：X-API-Token: <token>

运行：
    python -m tools.token_generator
"""

from db_utils import init_db, list_active_plans
from services.member_service import create_or_get_user, get_or_create_api_key, open_subscription


def _input_optional(prompt: str):
    value = input(prompt).strip()
    return value or None


def _choose_plan() -> str:
    plans = list_active_plans()
    if not plans:
        raise RuntimeError("套餐表为空，请先运行：python -m tools.db.init_plans")

    print("\n可用套餐：")
    for idx, plan in enumerate(plans, start=1):
        price = int(plan.get("sale_price_cent") or 0) / 100
        print(
            f"{idx}. {plan['plan_name']} | {plan['plan_code']} | "
            f"{plan['duration_days']}天 | {price:.2f}元"
        )

    while True:
        text = input("\n请选择套餐序号或直接输入 plan_code：").strip()
        if not text:
            print("❌ 套餐不能为空")
            continue

        if text.isdigit():
            idx = int(text)
            if 1 <= idx <= len(plans):
                return plans[idx - 1]["plan_code"]

        for plan in plans:
            if text == plan["plan_code"]:
                return plan["plan_code"]

        print("❌ 套餐不存在，请重新输入")


def create_member_token(
    username=None,
    phone=None,
    email=None,
    taobao_nick=None,
    plan_code="general_month",
    taobao_order_no=None,
    amount_cent=None,
    promo_name=None,
    remark=None,
):
    init_db()
    user = create_or_get_user(
        username=username,
        phone=phone,
        email=email,
        taobao_nick=taobao_nick,
    )
    token = get_or_create_api_key(user["id"])
    subscription = open_subscription(
        user_id=user["id"],
        plan_code=plan_code,
        taobao_order_no=taobao_order_no,
        amount_cent=amount_cent,
        promo_name=promo_name,
        remark=remark,
    )
    return {"user": user, "token": token, "subscription": subscription}


if __name__ == "__main__":
    print("=" * 70)
    print("📌 股票API会员 Token 生成工具（单 Token / 新会员体系）")
    print("📌 写入表：users + api_keys + subscriptions + plans")
    print("📌 请求头：X-API-Token: 你的Token")
    print("=" * 70)

    init_db()

    username = _input_optional("1. 用户名称，可空：")
    phone = _input_optional("2. 手机号，推荐填写，用于查重，可空：")
    email = _input_optional("3. 邮箱，可空：")
    taobao_nick = _input_optional("4. 淘宝昵称，手机号为空时建议填写，可空：")

    if not phone and not email and not taobao_nick:
        print("❌ 手机号、邮箱、淘宝昵称至少填写一个，避免重复建用户。")
        raise SystemExit(1)

    plan_code = _choose_plan()
    taobao_order_no = _input_optional("5. 淘宝订单号，可空：")

    amount_cent = None
    amount_text = input("6. 实际收款金额，单位分，可空，例如 1990：").strip()
    if amount_text:
        try:
            amount_cent = int(amount_text)
        except ValueError:
            print("❌ 金额必须是整数分，例如 1990")
            raise SystemExit(1)

    promo_name = _input_optional("7. 优惠名称，可空：")
    remark = _input_optional("8. 备注，可空：")

    try:
        result = create_member_token(
            username=username,
            phone=phone,
            email=email,
            taobao_nick=taobao_nick,
            plan_code=plan_code,
            taobao_order_no=taobao_order_no,
            amount_cent=amount_cent,
            promo_name=promo_name,
            remark=remark,
        )
    except Exception as e:
        print(f"❌ 生成失败：{e}")
        raise SystemExit(1)

    user = result["user"]
    sub = result["subscription"]
    token = result["token"]

    print("\n" + "=" * 70)
    print("✅ 会员 Token 生成/续费成功")
    print(f"用户ID：{user['id']}")
    print(f"套餐：{sub['plan_name']} ({sub['plan_code']})")
    print(f"开始时间：{sub['start_time']}")
    print(f"到期时间：{sub['expire_time']}")
    print(f"X-API-Token：{token}")
    print("=" * 70)
