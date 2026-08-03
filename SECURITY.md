# 安全政策

## 支持的版本

安全更新仅针对当前最新版本（`main` 分支的最新提交及最近发布的版本）。请尽量升级到最新版本后再报告问题。

## 报告安全漏洞

**请不要通过公开 Issue 报告安全漏洞。**

请优先使用 GitHub 私有安全通告（Security Advisory）报告：

- https://github.com/dragan2023/creative-master-cloud/security/advisories/new

也可通过邮件私密联系维护者：`zjlkfc007@gmail.com`

请在报告中包含：

- 受影响的版本与运行环境；
- 漏洞类型与危害描述；
- 复现步骤（尽量精简）；
- 如可能，附上修复建议或补丁。

## 处理流程

1. 维护者在 48 小时内确认收到报告并评估影响；
2. 确认漏洞后尽快修复并发布修复版本；
3. 修复发布后公开披露漏洞详情（若适用），并致谢报告者。

## 安全最佳实践

- 真实密钥（`SECRET_KEY`、API Key、数据库口令、管理员口令等）只放在本地 `.env` / `.env.cloud`，**严禁提交到仓库**。
- 生产环境必须更换默认的 `SECRET_KEY` 与管理员口令（参见 `.env.cloud.example` 中的说明）。
- 仓库中的环境变量模板只包含占位符，部署时请使用强随机值。
- 对外暴露服务前请配置 HTTPS（参考 `nginx/ssl-setup.sh`）并收紧 `CORS_ORIGINS`。
