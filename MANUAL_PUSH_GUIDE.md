# 手动推送指南

**问题**: Git push 持续遇到 HTTP 408 超时错误  
**原因**: 网络连接不稳定或 GitHub 服务器负载高  
**状态**: 所有代码已在本地完成并测试通过

---

## 🎯 当前状态

### 本地提交（14个）
```
00ee6cec chore: 从版本控制中移除 node_modules
ac640b5a docs: 添加 M5 完整补全验收测试报告  
000e81ca docs: 增加 M5 测试结论报告
7f3b0e37 fix(frontend): 修复算法页面空白问题
517058b2 feat(frontend): M5 完整补全 - 阵列误差/高级参数/场景预览增强
dd2b287c docs: 更新 M5 里程碑报告（完整版）
91f56c9a Merge milestone/m5-complete: 前端界面完整版
... (共 14 个)
```

### 标签
```
v0.6.0-m5-complete
```

---

## 📋 推荐方案：使用 GitHub Desktop

### 步骤 1: 安装 GitHub Desktop（如未安装）
下载：https://desktop.github.com/

### 步骤 2: 打开项目
1. 打开 GitHub Desktop
2. File → Add Local Repository
3. 选择 `D:\10_Projects\DOA_Estimation\Arena`

### 步骤 3: 推送
1. 在 GitHub Desktop 中查看 14 个待推送的提交
2. 点击右上角 **"Push origin"** 按钮
3. GitHub Desktop 会自动处理大文件和重试

✅ **优点**: GitHub Desktop 对网络问题有更好的处理

---

## 🔧 方案 2：使用 GitHub CLI

```bash
# 1. 确认已登录（已完成）
gh auth status

# 2. 使用 gh 推送（更稳定）
gh auth setup-git
git push origin main

# 3. 推送标签
git push origin v0.6.0-m5-complete
```

---

## 💻 方案 3：命令行手动推送

### Windows PowerShell

```powershell
# 1. 打开 PowerShell
cd D:\10_Projects\DOA_Estimation\Arena

# 2. 设置更长的超时
git config http.postBuffer 524288000
git config http.timeout 600
git config http.lowSpeedLimit 1000
git config http.lowSpeedTime 600

# 3. 推送（多次尝试）
git push origin main --verbose

# 如果失败，等待 5 分钟后重试
# GitHub 可能有临时的负载问题

# 4. 推送标签
git push origin v0.6.0-m5-complete
```

### Git Bash

```bash
cd /d/10_Projects/DOA_Estimation/Arena

# 使用 SSH（如果已配置 SSH 密钥）
git remote set-url origin git@github.com:saymynameww/doa-arena.git
git push origin main
git push origin v0.6.0-m5-complete

# 或继续使用 HTTPS
git remote set-url origin https://github.com/saymynameww/doa-arena.git
git push origin main
```

---

## ⏰ 方案 4：稍后重试

GitHub 服务器负载在不同时间段有差异：

**建议重试时间**:
- ✅ 早上 6:00-9:00（服务器负载低）
- ✅ 晚上 22:00-23:00（国内访问高峰过后）
- ❌ 避免 18:00-21:00（高峰时段）

**重试命令**:
```bash
git push origin main
```

---

## 🔍 验证推送成功

### 方法 1: 检查 GitHub 网页
访问：https://github.com/saymynameww/doa-arena

查看：
- ✅ 最新提交是 `chore: 从版本控制中移除 node_modules`
- ✅ 提交数量增加了 14 个
- ✅ 标签 `v0.6.0-m5-complete` 出现

### 方法 2: 命令行验证
```bash
git fetch origin
git status

# 应该显示：
# Your branch is up to date with 'origin/main'.
```

---

## 📊 推送内容摘要

### 关键更改
1. **M5 完整补全**
   - 阵列误差配置（4种误差）
   - 高级参数折叠
   - 场景预览动态范围

2. **Bug 修复**
   - 算法页面空白问题

3. **文档**
   - 完整验收测试报告
   - M5 完成度更新

4. **清理**
   - 移除 node_modules（减小仓库大小）

### 文件统计
```
新增文件: 4 个
修改文件: 12 个
删除文件: 28313 个（node_modules）
新增代码: ~1000 行
删除代码: ~2.3M 行（node_modules）
```

---

## ⚠️ 重要提示

1. **不要强制推送**: 避免使用 `git push --force`
2. **保持本地更改**: 所有工作已安全保存在本地
3. **可以继续开发**: 推送问题不影响本地工作
4. **node_modules 已清理**: 下次推送会更快

---

## 🆘 如果所有方法都失败

### 最后手段：创建新分支推送

```bash
# 1. 创建新分支
git checkout -b m5-complete-final

# 2. 推送新分支
git push origin m5-complete-final

# 3. 在 GitHub 上创建 Pull Request
# 访问：https://github.com/saymynameww/doa-arena
# 点击 "Compare & pull request"
# 标题：M5 完整补全 + Bug 修复
# 合并到 main

# 4. 合并后删除本地分支
git checkout main
git pull origin main
git branch -d m5-complete-final
```

---

## 📞 需要帮助？

如果以上方法都不奏效，可能的原因：
1. 本地网络限制
2. GitHub 服务临时故障
3. 仓库权限问题

**检查清单**:
- [ ] 网络连接正常
- [ ] GitHub 服务状态：https://www.githubstatus.com/
- [ ] 有仓库推送权限
- [ ] Git 版本是最新的

---

**记住**: 所有更改都安全保存在本地，慢慢推送也没问题！✅
