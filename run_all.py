# -*- coding: utf-8 -*-
"""总控脚本：按顺序跑完所有6个账号。"""
import subprocess
import sys
import os

# 账号列表
accounts = [
    # (名称, URL)
    ("账号1", "https://www.douyin.com/user/MS4wLjABAAAAu09iJGJ3vYEdzL2lMJuz8UNDuedVCOCQ35E98POwRJw?from_tab_name=main"),
    ("账号2", "https://www.douyin.com/user/MS4wLjABAAAAf-f-nvkpElh5Zry0HnVYQ3_H7FAp-e10a-Lyy1X67C0?from_tab_name=main"),
    ("账号3", "https://www.douyin.com/user/MS4wLjABAAAAg9-bFoh1uKBQgcmF_5koQllv8fFSkhwABNCRoIE8Z7Xb8vygWzARt1mNFZL8dzBw?from_tab_name=main"),
    ("账号4", "https://www.douyin.com/user/MS4wLjABAAAAruH-P_H8WDZ1GFcxRkuHP61n9gqyQTuHCtxCzodBEM6DbrQn4wqM2kGmKy9rIFSG?from_tab_name=main"),
    ("账号5", "https://www.douyin.com/user/MS4wLjABAAAACrUo6FpCr9_nFMMU2clRi9gDAft7Y6MIsj9Rg5StMgAhNAZdALl5pwsQKbdtcBsU?from_tab_name=main"),
    ("账号6", "https://www.douyin.com/user/MS4wLjABAAAAtVJsTUwEBZD9I1ZL5TsZrowBB1Xc81vcHafjlOVSKgP3DV2PA1vmm0dNW689CAuy?from_tab_name=main"),
]

python_exe = ".\\.venv\\Scripts\\python.exe"

# 先跑1号修复脚本
print("=" * 50)
print("开始处理账号1...")
print("=" * 50)
subprocess.run([python_exe, "fix_account1.py"], check=False)

# 再跑2-6号
for i, (name, url) in enumerate(accounts[1:], start=2):
    print("\n" + "=" * 50)
    print(f"开始处理账号{i}...")
    print("=" * 50)
    subprocess.run([python_exe, "run_account.py", url], check=False)

print("\n" + "=" * 50)
print("全部账号处理完成！")
print("=" * 50)
