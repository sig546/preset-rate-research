#!/usr/bin/env python3
"""
GitHub Pages 一键部署脚本
使用方法：
  1. 注册 GitHub 账户
  2. 创建 Personal Access Token（勾选 repo 权限）
  3. 运行此脚本：python deploy_to_github.py
"""

import subprocess
import sys
import os
import json
import urllib.request
import urllib.error

REPO_NAME = "preset-rate-research"
REPO_DESC = "预定利率研究值 - 历史数据·预测·触发分析"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

def run_git(*args):
    """Run a git command and return output."""
    result = subprocess.run(
        ["git"] + list(args),
        cwd=PROJECT_DIR,
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"  [ERROR] git {' '.join(args)}")
        print(f"  {result.stderr.strip()}")
        return False, result.stdout
    return True, result.stdout.strip()

def create_repo(username, token, repo_name, description):
    """Create a new GitHub repository via API."""
    url = "https://api.github.com/user/repos"
    data = json.dumps({
        "name": repo_name,
        "description": description,
        "private": False,
        "auto_init": False
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return True, result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        return False, json.loads(error_body)

def enable_pages(username, token, repo_name):
    """Enable GitHub Pages via API."""
    url = f"https://api.github.com/repos/{username}/{repo_name}/pages"
    data = json.dumps({
        "build_type": "workflow"
    }).encode("utf-8")

    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Authorization", f"token {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return True, result
    except urllib.error.HTTPError as e:
        if e.code == 409:
            # Pages already enabled
            return True, {"message": "Pages already enabled"}
        error_body = e.read().decode("utf-8")
        return False, json.loads(error_body)

def main():
    print("=" * 60)
    print("  GitHub Pages 一键部署脚本")
    print("  预定利率研究值网站")
    print("=" * 60)
    print()

    # Step 1: Get credentials
    print("[1/5] 请输入 GitHub 账户信息")
    username = input("  GitHub 用户名: ").strip()
    token = input("  Personal Access Token: ").strip()

    if not username or not token:
        print("  [ERROR] 用户名和 Token 不能为空")
        sys.exit(1)

    print()

    # Step 2: Configure git
    print("[2/5] 配置 Git 用户信息")
    run_git("config", "user.name", username)
    run_git("config", "user.email", f"{username}@users.noreply.github.com")
    print(f"  user.name = {username}")
    print()

    # Step 3: Create GitHub repository
    print("[3/5] 创建 GitHub 仓库")
    success, result = create_repo(username, token, REPO_NAME, REPO_DESC)
    if not success:
        if "already exists" in str(result.get("errors", "")):
            print(f"  仓库 {REPO_NAME} 已存在，继续使用")
        else:
            print(f"  [ERROR] 创建仓库失败: {result}")
            sys.exit(1)
    else:
        print(f"  仓库创建成功: {result.get('html_url', 'N/A')}")
    print()

    # Step 4: Push code
    print("[4/5] 推送代码到 GitHub")
    remote_url = f"https://{username}:{token}@github.com/{username}/{REPO_NAME}.git"

    # Remove existing remote if any
    run_git("remote", "remove", "origin")
    run_git("remote", "add", "origin", remote_url)
    print("  远程仓库已关联")

    success, output = run_git("push", "-u", "origin", "main")
    if not success:
        print("  [ERROR] 推送失败，请检查网络和认证信息")
        sys.exit(1)
    print("  代码推送成功")
    print()

    # Step 5: Enable GitHub Pages
    print("[5/5] 启用 GitHub Pages")
    success, result = enable_pages(username, token, REPO_NAME)
    if success:
        print("  GitHub Pages 已启用（使用 GitHub Actions）")
    else:
        print(f"  [WARNING] 自动启用 Pages 失败: {result}")
        print("  请手动操作: 仓库 Settings > Pages > Source 选择 'GitHub Actions'")
    print()

    # Done
    pages_url = f"https://{username}.github.io/{REPO_NAME}/"
    print("=" * 60)
    print("  部署完成！")
    print(f"  仓库地址: https://github.com/{username}/{REPO_NAME}")
    print(f"  网站地址: {pages_url}")
    print("  （首次部署约需 1-2 分钟生效）")
    print("=" * 60)

if __name__ == "__main__":
    main()
