# GitHub 上传与回滚指南

本项目已在本地初始化为 git 仓库（首次提交 c730288），并配置好与 GitHub 的
连接（openssl + CA 证书）。下面教你上传和回滚。

## 一、准备：注册 GitHub 账号

1. 打开 https://github.com ，点 **Sign up** 注册（用户名 + 邮箱 + 密码）。
2. 注册后记住你的**用户名**（GitHub 页面左上角显示的那个）。

## 二、在 GitHub 网页上创建空仓库

1. 登录后点右上角 **+** → **New repository**。
2. 填仓库名，例如 `bili-tab-extractor`（英文、无空格）。
3. 可见性选 **Private**（私有，只有你能看）或 **Public**（公开）。
4. **不要**勾选 "Add a README" / ".gitignore" / "license"（我们本地已建好，避免冲突）。
5. 点 **Create repository**。

## 三、把本地项目推送到 GitHub

### 方式 A：命令行（推荐，本机已配好连接）

在项目文件夹（`C:\Users\20849\Desktop\视频扒谱`）打开命令行，执行：

```bash
# 1. 把本地的 main 分支改名为 main（GitHub 默认主分支名）
git branch -M main

# 2. 关联远程仓库（换成你的用户名和仓库名）
git remote add origin https://github.com/你的用户名/bili-tab-extractor.git

# 3. 推送（第一次需要输入 GitHub 账号密码）
#    注意：密码框要填 "Personal Access Token"（见下方说明），不是登录密码
git push -u origin main
```

**第一次 push 的认证**：GitHub 已不支持用登录密码 push，需要用 **Token**：
1. GitHub 网页 → 头像 → **Settings** → 左下角 **Developer settings** → **Personal access tokens** → **Tokens (classic)** → **Generate new token**。
2. 勾选 `repo` 权限，生成一串 `ghp_...` 开头的 token，复制保存。
3. push 时用户名填你的 GitHub 用户名，密码粘贴这个 token。
4. 之后再次 push 一般会记住（Windows 凭据管理器）。

### 方式 B：GitHub Desktop（图形化，适合新手）

1. 下载安装 https://desktop.github.com ，用 GitHub 账号登录。
2. 菜单 **File → Add local repository** → 选择 `C:\Users\20849\Desktop\视频扒谱`。
3. 窗口里能看到你的提交历史；点 **Publish repository** 即可上传到 GitHub。
4. 之后修改代码，在 Desktop 里填写摘要点 **Commit**，再点 **Push origin**。

## 四、日常更新流程（每次改完代码）

```bash
git status            # 看改了哪些文件
git add .             # 暂存所有改动
git commit -m "说明这次改了什么"   # 提交
git push              # 推到 GitHub
```

## 五、出问题回滚到历史版本

### 1. 查看历史版本

```bash
git log --oneline        # 列出所有提交（每行一个，前面是版本号）
git log --oneline -10    # 只看最近 10 条
```

### 2. 回滚方式一：git reset（抹掉之后的所有提交）

```bash
# 回到某个版本，且丢弃之后的所有改动（慎用！）
git reset --hard <版本号>

# 例如回到首次提交
git reset --hard c730288

# 回滚后强制推送（覆盖远程）：
git push --force
```

### 3. 回滚方式二：git revert（保留历史，新增一个"撤销"提交）—— 推荐

```bash
# 撤销某次提交的影响，但保留历史记录（更安全）
git revert <版本号>
git push
```

### 4. 网页回滚（最直观，GitHub Desktop 也支持）

1. GitHub 仓库页面 → **Commits**（提交历史）。
2. 找到要回滚的版本 → 点 **Browse files** 可查看当时代码；
   点 `...` → **Revert** 即可一键撤销该提交并生成新提交。

### 5. 回滚前先备份当前工作

```bash
git stash        # 临时保存未提交的改动
git reset --hard <版本号>
```

## 六、小贴士

- **每次 push 前先 pull**（如果多台电脑改过）：`git pull`
- `.gitignore` 已排除 exe/视频/依赖等大文件，仓库保持轻量；
  别人克隆后用 `pip install -r requirements.txt` 即可运行。
- 本机 git 已配置 openssl + CA 证书用于连 GitHub（本地仓库配置，重装系统需重新配）。
