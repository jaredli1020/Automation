#!/bin/bash
# ============================================================
# 自动化测试框架 - 服务器初始化脚本
# 适用系统: CentOS / veLinux
# 用法: sudo bash init_server.sh
# ============================================================

set -e

echo "=========================================="
echo "  自动化测试框架 - 服务器初始化"
echo "=========================================="

# ---------- 1. 系统基础配置 ----------
echo "[1/5] 系统基础配置..."

if [ -f /etc/selinux/config ]; then
    sed -i 's/SELINUX=enforcing/SELINUX=disabled/g' /etc/selinux/config
    setenforce 0 2>/dev/null || true
    echo "  SELinux 已关闭"
fi

systemctl stop firewalld 2>/dev/null || true
systemctl disable firewalld 2>/dev/null || true
echo "  防火墙已关闭（测试环境，生产环境请用安全组替代）"

timedatectl set-timezone Asia/Shanghai
echo "  时区已设置为 Asia/Shanghai"

# ---------- 2. 安装基础工具 ----------
echo "[2/5] 安装基础工具..."
yum install -y yum-utils device-mapper-persistent-data lvm2 \
    git curl wget vim net-tools

# ---------- 3. 安装 Docker ----------
echo "[3/5] 安装 Docker..."

if command -v docker &>/dev/null; then
    echo "  Docker 已安装，跳过"
else
    yum-config-manager --add-repo https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo
    yum install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<'EOF'
{
    "registry-mirrors": [
        "https://mirror.ccs.tencentyun.com",
        "https://docker.mirrors.ustc.edu.cn"
    ],
    "log-driver": "json-file",
    "log-opts": {
        "max-size": "100m",
        "max-file": "3"
    },
    "storage-driver": "overlay2"
}
EOF

    systemctl start docker
    systemctl enable docker
    echo "  Docker 安装完成"
fi

docker --version

# ---------- 4. 安装 Docker Compose ----------
echo "[4/5] 安装 Docker Compose..."

if command -v docker-compose &>/dev/null; then
    echo "  Docker Compose 已安装，跳过"
else
    if docker compose version &>/dev/null; then
        echo '#!/bin/bash' > /usr/local/bin/docker-compose
        echo 'docker compose "$@"' >> /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        echo "  Docker Compose (plugin) 已就绪"
    else
        curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
            -o /usr/local/bin/docker-compose
        chmod +x /usr/local/bin/docker-compose
        echo "  Docker Compose 独立版安装完成"
    fi
fi

docker-compose --version || docker compose version

# ---------- 5. 创建项目目录结构 ----------
echo "[5/5] 创建项目目录..."

PROJECT_HOME=/opt/autotest-ci
mkdir -p ${PROJECT_HOME}/test-reports

echo "  项目目录: ${PROJECT_HOME}"
echo ""
echo "=========================================="
echo "  初始化完成！"
echo "  下一步:"
echo "    cd ${PROJECT_HOME}"
echo "    git clone <YOUR_REPO_URL> autotest-framework"
echo "    cd autotest-framework"
echo "    docker build -t autotest-framework -f deploy/Dockerfile ."
echo "    docker-compose -f deploy/docker-compose.yml up -d"
echo "=========================================="
