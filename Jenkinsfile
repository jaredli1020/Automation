pipeline {
    agent { label 'built-in' }

    environment {
        TEST_IMAGE = 'autotest-framework:latest'
        GIT_REPO = 'YOUR_GIT_REPO_URL'
        HOST_REPORT_DIR = '/opt/autotest-ci/test-reports'
    }

    parameters {
        choice(name: 'BUSINESS', choices: ['demo'], description: '业务模块')
        choice(name: 'TEST_TARGET', choices: ['api', 'all'], description: '测试类型')
        choice(name: 'ENV', choices: ['prod', 'test'], description: '运行环境')
        booleanParam(name: 'NOTIFY', defaultValue: true, description: '是否发送飞书通知')
    }

    stages {
        stage('Checkout') {
            steps {
                git url: "${GIT_REPO}", branch: 'master'
            }
        }

        stage('Build Image') {
            steps {
                sh "docker build -t ${TEST_IMAGE} -f deploy/Dockerfile ."
            }
        }

        stage('API Test') {
            when {
                expression { params.TEST_TARGET in ['api', 'all'] }
            }
            steps {
                script {
                    def notifyFlag = params.NOTIFY ? '' : '--no-notify'

                    sh """
                        mkdir -p reports
                        docker run --rm \
                            -v ${HOST_REPORT_DIR}:/app/reports \
                            -e ENV=${params.ENV} \
                            -e REPORT_BASE_URL=http://localhost:8000 \
                            ${TEST_IMAGE} \
                            python run_test.py ${params.BUSINESS}:api --env ${params.ENV} ${notifyFlag} || true
                    """
                }
            }
            post {
                always {
                    sh "cp ${HOST_REPORT_DIR}/*.html reports/ 2>/dev/null || true"
                    archiveArtifacts artifacts: 'reports/*.html', allowEmptyArchive: true
                }
            }
        }

        stage('Restart Test Server') {
            steps {
                script {
                    sh '''
                        docker stop autotest-server || true
                        docker rm autotest-server || true

                        docker run -d \
                            --name autotest-server \
                            --restart always \
                            -e ENV=prod \
                            -e TZ=Asia/Shanghai \
                            -e REPORT_BASE_URL=http://localhost:8000 \
                            -p 8000:8000 \
                            -v /opt/autotest-ci/test-reports:/app/reports \
                            autotest-framework:latest
                    '''
                    echo '测试服务已用新镜像重建'
                }
            }
        }
    }

    post {
        failure {
            echo '测试执行失败，请检查日志'
        }
        success {
            echo '测试执行完成'
        }
    }
}
