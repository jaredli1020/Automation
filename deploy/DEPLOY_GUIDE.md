# 自动化测试框架 - 部署指南

> 适用场景: 本地 Docker 开发 + Jenkins CI 对接

---

## 整体架构

```
┌──────────────────────────────────────────────────────┐
│              服务器                                    │
│                                                      │
│  ┌────────────────┐    ┌──────────────────────────┐  │
│  │ 测试服务 :8000  │    │ Docker 容器（测试执行）    │  │
│  │ Django + 定时   │    │ Jenkins 构建时按需创建    │  │
│  └────────────────┘    └──────────────────────────┘  │
└──────────────────────────────────────────────────────┘
        ▲                          ▲
        │ HTTP 触发                 │ 构建调度
        │                          │
┌───────┴──────┐           ┌───────┴──────┐
│   GitLab     │──Webhook─▶│   Jenkins    │
└──────────────┘           └──────────────┘
```

- GitLab: 代码托管 + Webhook 触发构建
- Jenkins: CI 调度，API 测试在 Docker 容器内执行
- 测试服务 (`:8000`): Django 常驻服务，提供 HTTP 接口触发测试 + 定时自动执行

---

## 本地开发（Phase 1）

### 前置条件

- Docker Desktop 已安装
- Docker Compose 可用

### 1. 构建镜像

```bash
cd E:\PythonProject\automation_framework
docker build -t autotest-framework -f deploy/Dockerfile .
```

### 2. 验证服务模式

```bash
docker run -d --name autotest-server -p 8000:8000 \
  -e ENV=prod \
  -e REPORT_BASE_URL=http://localhost:8000 \
  autotest-framework

# 健康检查
curl http://localhost:8000/api/health

# 查看可用模块
curl http://localhost:8000/api/modules

# 停止
docker stop autotest-server && docker rm autotest-server
```

### 3. 验证测试执行模式

```bash
docker run --rm \
  -v "$(pwd)/reports:/app/reports" \
  -e ENV=prod \
  autotest-framework \
  python run_test.py demo:api --env prod --no-notify

# 检查报告是否生成
ls reports/*.html
```

### 4. 使用 docker-compose

```bash
# 启动
docker-compose -f deploy/docker-compose.yml up -d

# 查看日志
docker-compose -f deploy/docker-compose.yml logs -f

# 停止
docker-compose -f deploy/docker-compose.yml down
```

---

## 服务器部署（Phase 3）

### 1. 初始化服务器

```bash
# 上传 deploy 目录到服务器
scp -O -r deploy/ root@YOUR_SERVER_IP:/root/

# SSH 登录
ssh root@YOUR_SERVER_IP

# 执行初始化脚本
cd /root/deploy
chmod +x init_server.sh
bash init_server.sh
```

### 2. 克隆代码并构建

```bash
cd /opt/autotest-ci
git clone YOUR_GIT_REPO_URL autotest-framework
cd autotest-framework
docker build -t autotest-framework -f deploy/Dockerfile .
```

### 3. 启动服务

```bash
cp deploy/docker-compose.yml /opt/autotest-ci/
cd /opt/autotest-ci

# 修改 REPORT_BASE_URL 为服务器 IP
# vim docker-compose.yml

docker-compose up -d
```

### 4. 验证

```bash
docker ps | grep autotest-server
curl http://localhost:8000/api/health
```

---

## Jenkins 配置（Phase 2）

### 1. 安装插件

Jenkins → Manage Jenkins → Plugins → Available plugins:

- Git
- Pipeline
- Docker Pipeline
- HTML Publisher

### 2. 创建 Pipeline Job

1. New Item → 名称 `autotest-api` → Pipeline → OK
2. 配置:
   - **Build Triggers**: 勾选 `Build periodically`，Schedule: `0 8 * * *`
   - **Pipeline**:
     - Definition: `Pipeline script from SCM`
     - SCM: Git
     - Repository URL: 你的仓库地址
     - Branch: `*/master`
     - Script Path: `Jenkinsfile`
3. Save

### 3. 修改 Jenkinsfile

打开 `Jenkinsfile`，修改以下变量:

```groovy
environment {
    GIT_REPO = 'YOUR_GIT_REPO_URL'           // ← 改为实际仓库地址
    HOST_REPORT_DIR = '/opt/autotest-ci/test-reports'  // ← 报告目录
}
```

`Restart Test Server` 阶段中的 `REPORT_BASE_URL` 改为服务器 IP。

### 4. 首次构建

> 首次构建时 Jenkins 还没读取到参数定义，左侧只有 `Build Now`。
> 先点一次 `Build Now`（不管成功失败），刷新页面后就会出现 `Build with Parameters`。

### 5. 配置 Webhook（可选）

GitLab 项目 → Settings → Webhooks:
- URL: `http://用户名:APIToken@JENKINS_URL/project/autotest-api`
- Trigger: Push events
- 取消 SSL verification

---

## 常用运维命令

```bash
# 查看服务状态
docker ps | grep autotest-server

# 查看日志
docker logs -f autotest-server

# 重启服务
docker restart autotest-server

# 更新代码并重建
cd /opt/autotest-ci/autotest-framework
git pull
docker build -t autotest-framework -f deploy/Dockerfile .
docker stop autotest-server && docker rm autotest-server
cd /opt/autotest-ci && docker-compose up -d

# 清理无用镜像
docker system prune -f
```

---

## 安全组端口

| 端口 | 用途 | 协议 |
|------|------|------|
| 22 | SSH | TCP |
| 8000 | 测试服务 | TCP |

---

## 扩展说明

### 添加新业务模块

1. 在 `run_test.py` 的 `BUSINESS_MODULES` 列表中添加模块名
2. 在 `Jenkinsfile` 的 `BUSINESS` 参数 choices 中添加
3. 无需修改 Dockerfile 或 docker-compose

### 后续添加 UI 测试

1. Dockerfile 中添加: `RUN playwright install --with-deps chromium`
2. Jenkinsfile 中 `TEST_TARGET` choices 添加 `'ui'`
3. 添加 UI Test stage（参考 IdreamSky 项目的 Jenkinsfile）
