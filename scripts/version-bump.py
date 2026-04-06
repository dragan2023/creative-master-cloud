#!/usr/bin/env python3
"""
版本自动递增脚本

根据 Git 提交信息自动判断版本递增类型，更新 version.json 和 CHANGELOG.md

使用方法:
    python scripts/version-bump.py [--dry-run] [--type major|minor|patch]

人工干预标记 (在提交信息中添加):
    [skip version]  - 跳过版本更新
    [major]         - 强制 MAJOR 递增
    [minor]         - 强制 MINOR 递增
    [patch]         - 强制 PATCH 递增
    [version:X.Y.Z] - 指定具体版本号

@date: 2026-04-07
@author: Qoder
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


class VersionBump:
    """版本自动递增管理器"""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.version_file = project_root / "version.json"
        self.changelog_file = project_root / "CHANGELOG.md"
        self.readme_file = project_root / "README.md"
        self.frontend_version_file = project_root / "frontend/src/config/version.js"
        self.frontend_package_file = project_root / "frontend/package.json"

    def get_current_version(self) -> str:
        """获取当前版本号"""
        if not self.version_file.exists():
            return "1.0.0"

        with open(self.version_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("current_version", "1.0.0")

    def parse_version(self, version: str) -> Tuple[int, int, int]:
        """解析版本号为元组"""
        match = re.match(r"(\d+)\.(\d+)\.(\d+)", version)
        if not match:
            return (1, 0, 0)
        return tuple(int(x) for x in match.groups())

    def increment_version(
        self,
        current: str,
        bump_type: str
    ) -> str:
        """递增版本号"""
        major, minor, patch = self.parse_version(current)

        if bump_type == "major":
            return f"{major + 1}.0.0"
        elif bump_type == "minor":
            return f"{major}.{minor + 1}.0"
        else:  # patch
            return f"{major}.{minor}.{patch + 1}"

    def get_commits_since_last_push(self) -> list:
        """获取自上次推送以来的提交"""
        try:
            # 获取远程分支的最新提交
            result = subprocess.run(
                ["git", "fetch", "--dry-run"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )

            # 获取未推送的提交
            result = subprocess.run(
                ["git", "log", "@{u}..HEAD",
                    "--oneline", "--pretty=format:%s"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )

            if result.returncode != 0:
                # 如果没有上游分支，获取最近5次提交
                result = subprocess.run(
                    ["git", "log", "-5", "--oneline", "--pretty=format:%s"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root
                )

            commits = result.stdout.strip().split("\n") if result.stdout.strip() else []
            return [c for c in commits if c]
        except Exception:
            return []

    def get_changed_files_stats(self) -> dict:
        """获取变更文件统计"""
        try:
            result = subprocess.run(
                ["git", "diff", "--stat", "@{u}..HEAD"],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )

            if result.returncode != 0:
                result = subprocess.run(
                    ["git", "diff", "--stat", "HEAD~5..HEAD"],
                    capture_output=True,
                    text=True,
                    cwd=self.project_root
                )

            stats = {
                "total_files": 0,
                "insertions": 0,
                "deletions": 0,
                "backend_files": 0,
                "frontend_files": 0,
                "config_files": 0
            }

            if result.stdout:
                lines = result.stdout.strip().split("\n")
                for line in lines:
                    if "backend/" in line:
                        stats["backend_files"] += 1
                    elif "frontend/" in line:
                        stats["frontend_files"] += 1
                    elif any(x in line for x in [".env", ".json", ".yml", ".yaml", ".toml"]):
                        stats["config_files"] += 1
                    stats["total_files"] += 1

            return stats
        except Exception:
            return {"total_files": 0, "insertions": 0, "deletions": 0}

    def determine_bump_type(self, commits: list, stats: dict) -> str:
        """
        根据提交信息和变更统计判断版本递增类型

        返回: "major", "minor" 或 "patch"
        """
        if not commits:
            return "patch"

        # 检查人工干预标记
        all_commits = " ".join(commits)

        # 检查跳过标记
        if "[skip version]" in all_commits:
            return "skip"

        # 检查强制指定版本号
        version_match = re.search(r"\[version:(\d+\.\d+\.\d+)\]", all_commits)
        if version_match:
            return f"specific:{version_match.group(1)}"

        # 检查强制类型标记
        if "[major]" in all_commits:
            return "major"
        if "[minor]" in all_commits:
            return "minor"
        if "[patch]" in all_commits:
            return "patch"

        # 自动判断
        for commit in commits:
            commit_lower = commit.lower()

            # MAJOR: 破坏性变更
            if any(x in commit for x in ["BREAKING CHANGE", "!:"]):
                return "major"

            # MINOR: 新功能
            if commit.startswith("feat") or commit.startswith("feat:"):
                return "minor"

            # 检查是否有删除核心文件的变更
            if "remove" in commit_lower and any(x in commit_lower for x in ["api", "service", "model", "endpoint"]):
                return "major"

        # 根据变更规模判断
        if stats.get("config_files", 0) > 3:
            return "minor"

        if stats.get("total_files", 0) > 10:
            return "minor"

        return "patch"

    def generate_update_notes(self, commits: list, bump_type: str) -> str:
        """生成更新说明"""
        if not commits:
            return f"## v{self.get_current_version()}\n\n常规更新和维护"

        # 分类提交
        features = []
        optimizations = []
        fixes = []
        improvements = []

        for commit in commits:
            commit_lower = commit.lower()

            if commit.startswith("feat") or "新增" in commit or "添加" in commit:
                features.append(commit)
            elif commit.startswith("fix") or "修复" in commit:
                fixes.append(commit)
            elif "优化" in commit or "improve" in commit_lower or "refactor" in commit_lower:
                optimizations.append(commit)
            else:
                improvements.append(commit)

        # 生成更新说明
        lines = []

        if features:
            lines.append("### 新增功能")
            for f in features[:5]:  # 最多5条
                # 清理提交信息前缀
                clean_msg = re.sub(r"^(feat|feature)[\(:\s]*", "", f).strip()
                lines.append(f"- {clean_msg}")
            lines.append("")

        if optimizations:
            lines.append("### 功能优化")
            for o in optimizations[:5]:
                clean_msg = re.sub(
                    r"^(optimize|refactor|perf)[\(:\s]*", "", o).strip()
                lines.append(f"- {clean_msg}")
            lines.append("")

        if fixes:
            lines.append("### 问题修复")
            for fx in fixes[:5]:
                clean_msg = re.sub(r"^(fix|bugfix)[\(:\s]*", "", fx).strip()
                lines.append(f"- {clean_msg}")
            lines.append("")

        if improvements:
            lines.append("### 稳定性改进")
            for i in improvements[:3]:
                lines.append(f"- {i}")

        return "\n".join(lines).strip()

    def update_version_json(self, new_version: str, update_notes: str) -> bool:
        """更新 version.json 文件"""
        if not self.version_file.exists():
            return False

        with open(self.version_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["current_version"] = new_version
        data["release_date"] = datetime.now().strftime("%Y-%m-%d")
        data["update_notes"] = f"## v{new_version}\n\n{update_notes}"

        with open(self.version_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

        return True

    def update_changelog(self, new_version: str, update_notes: str) -> bool:
        """更新 CHANGELOG.md 文件"""
        if not self.changelog_file.exists():
            return False

        with open(self.changelog_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 生成新版本条目
        new_entry = f"## [{new_version}] - {datetime.now().strftime('%Y-%m-%d')}\n\n{update_notes}\n\n---\n"

        # 在第一个版本条目之前插入
        # 查找 "## [" 模式
        match = re.search(r"\n## \[", content)
        if match:
            insert_pos = match.start() + 1
            new_content = content[:insert_pos] + \
                new_entry + content[insert_pos:]
        else:
            # 如果找不到版本条目格式，追加到文件末尾
            new_content = content + "\n" + new_entry

        with open(self.changelog_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        return True

    def update_readme(self, new_version: str) -> bool:
        """更新 README.md 中的版本信息"""
        if not self.readme_file.exists():
            return False

        with open(self.readme_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 更新版本号显示
        # 查找类似 "## v1.0.0" 或 "### v1.0.0" 的模式
        content = re.sub(
            r"(##\s*)v\d+\.\d+\.\d+",
            f"\\1v{new_version}",
            content,
            count=1
        )

        with open(self.readme_file, "w", encoding="utf-8") as f:
            f.write(content)

        return True

    def update_frontend_version(self, new_version: str) -> bool:
        """更新前端版本配置文件 frontend/src/config/version.js"""
        if not self.frontend_version_file.exists():
            return False

        with open(self.frontend_version_file, "r", encoding="utf-8") as f:
            content = f.read()

        # 更新 APP_VERSION 常量
        content = re.sub(
            r"export const APP_VERSION = ['\"]\d+\.\d+\.\d+['\"]",
            f"export const APP_VERSION = '{new_version}'",
            content
        )

        with open(self.frontend_version_file, "w", encoding="utf-8") as f:
            f.write(content)

        return True

    def update_package_json(self, new_version: str) -> bool:
        """更新 frontend/package.json 版本号"""
        if not self.frontend_package_file.exists():
            return False

        with open(self.frontend_package_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        data["version"] = new_version

        with open(self.frontend_package_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return True

    def commit_changes(self, new_version: str) -> bool:
        """提交版本更新变更"""
        try:
            # 添加变更的文件
            subprocess.run(
                ["git", "add",
                    "version.json",
                    "CHANGELOG.md",
                    "README.md",
                    "frontend/src/config/version.js",
                    "frontend/package.json"
                ],
                cwd=self.project_root,
                check=True
            )

            # 提交
            subprocess.run(
                ["git", "commit", "-m",
                    f"chore: bump version to {new_version} [skip ci]"],
                cwd=self.project_root,
                check=True
            )

            return True
        except subprocess.CalledProcessError:
            return False

    def run(
        self,
        dry_run: bool = False,
        force_type: Optional[str] = None
    ) -> dict:
        """
        执行版本更新

        Args:
            dry_run: 是否只预览不实际修改
            force_type: 强制指定递增类型

        Returns:
            包含执行结果的字典
        """
        result = {
            "success": False,
            "old_version": None,
            "new_version": None,
            "bump_type": None,
            "update_notes": None,
            "commits_analyzed": 0,
            "files_changed": 0,
            "message": ""
        }

        # 获取当前版本
        current_version = self.get_current_version()
        result["old_version"] = current_version

        # 获取提交和变更统计
        commits = self.get_commits_since_last_push()
        stats = self.get_changed_files_stats()
        result["commits_analyzed"] = len(commits)
        result["files_changed"] = stats.get("total_files", 0)

        # 判断递增类型
        if force_type:
            bump_type = force_type
        else:
            bump_type = self.determine_bump_type(commits, stats)

        result["bump_type"] = bump_type

        # 处理跳过或指定版本
        if bump_type == "skip":
            result["message"] = "版本更新已跳过（提交信息包含 [skip version]）"
            result["success"] = True
            return result

        if bump_type.startswith("specific:"):
            new_version = bump_type.split(":")[1]
        else:
            new_version = self.increment_version(current_version, bump_type)

        result["new_version"] = new_version

        # 生成更新说明
        update_notes = self.generate_update_notes(commits, bump_type)
        result["update_notes"] = update_notes

        if dry_run:
            result["message"] = f"预览模式：{current_version} -> {new_version} ({bump_type})"
            result["success"] = True
            return result

        # 执行更新
        try:
            self.update_version_json(new_version, update_notes)
            self.update_changelog(new_version, update_notes)
            self.update_readme(new_version)
            self.update_frontend_version(new_version)
            self.update_package_json(new_version)

            # 提交变更
            self.commit_changes(new_version)

            result["success"] = True
            result["message"] = f"版本已更新：{current_version} -> {new_version}"
        except Exception as e:
            result["message"] = f"更新失败：{str(e)}"

        return result


def main():
    """主函数"""
    import argparse

    parser = argparse.ArgumentParser(description="版本自动递增工具")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，不实际修改文件"
    )
    parser.add_argument(
        "--type",
        choices=["major", "minor", "patch"],
        help="强制指定递增类型"
    )

    args = parser.parse_args()

    # 确定项目根目录
    script_dir = Path(__file__).parent
    project_root = script_dir.parent

    # 执行版本更新
    bumper = VersionBump(project_root)
    result = bumper.run(dry_run=args.dry_run, force_type=args.type)

    # 输出结果
    print(f"\n{'='*50}")
    print(f"版本更新结果")
    print(f"{'='*50}")
    print(f"当前版本: {result['old_version']}")
    print(f"新版本号: {result['new_version']}")
    print(f"递增类型: {result['bump_type']}")
    print(f"分析提交: {result['commits_analyzed']} 条")
    print(f"变更文件: {result['files_changed']} 个")
    print(f"执行状态: {result['message']}")

    if result["update_notes"]:
        print(f"\n更新说明:\n{result['update_notes']}")

    print(f"{'='*50}\n")

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
