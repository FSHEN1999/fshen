import requests
import time
import random
import os

# --- 核心配置 ---
REQUEST_URL = "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/mock/generate-shop-performance"
REDIRECT_URL_PREFIX = "https://uat.api.expressfinance.business.hsbc.com/dpu-merchant/amazon/redirect?offerId="
HEADERS = {"Content-Type": "application/json"}
TIER_OPTIONS = {'1': ('TIER1', 120000), '2': ('TIER2', 950000), '3': ('TIER3', 2000000)}
FILE_PATH = r"D:\data\project\test\uat signup.txt"


def send_request(amount):
    """发送POST请求并返回提取到的amazon3plOfferId"""
    try:
        response = requests.post(REQUEST_URL, json={"yearlyRepaymentAmount": amount}, headers=HEADERS, timeout=10)
        response.raise_for_status()
        data = response.json()
        # 尝试从根节点或'data'子节点提取ID
        offer_id = data.get("amazon3plOfferId") or data.get("data", {}).get("amazon3plOfferId")
        return offer_id if isinstance(offer_id, str) else None
    except requests.exceptions.RequestException:
        return None
    except ValueError:  # JSON解析失败
        return None


def get_user_choice(prompt, valid_choices):
    """获取用户的有效输入"""
    while True:
        choice = input(prompt)
        if choice in valid_choices:
            return choice
        print(f"输入无效，请选择 {', '.join(valid_choices)}。")


def main():
    """主函数"""
    print("--- HSBC API 批量请求工具 ---")

    # 获取请求次数
    try:
        total = int(input("请输入请求次数: "))
        if total <= 0:
            print("请求次数必须大于0。")
            return
    except ValueError:
        print("请输入一个有效的数字。")
        return

    # 确保目录存在
    os.makedirs(os.path.dirname(FILE_PATH), exist_ok=True)

    for i in range(total):
        print(f"\n--- 第 {i + 1}/{total} 次请求 ---")

        # 选择TIER
        tier_choice = get_user_choice("请选择TIER (1/2/3): ", TIER_OPTIONS.keys())
        tier_name, amount = TIER_OPTIONS[tier_choice]

        # 发送请求
        print(f"正在发送请求 (TIER: {tier_name}, Amount: {amount})...")
        offer_id = send_request(amount)

        if offer_id:
            phone = f"182{random.randint(10000000, 99999999)}"
            full_url = f"{REDIRECT_URL_PREFIX}{offer_id}"

            # 写入文件
            with open(FILE_PATH, "a", encoding="utf-8") as f:
                f.write(f"{tier_name}\n{full_url}\n{phone}\n\n")

            print("成功！数据已保存。")
        else:
            print("请求失败或未获取到有效ID。")

        # 请求间隔（最后一次请求后不等待）
        if i < total - 1:
            time.sleep(1)  # 间隔1秒

    print(f"\n所有请求已完成。数据保存在: {FILE_PATH}")


if __name__ == "__main__":
    main()