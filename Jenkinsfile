pipeline {
    agent any

    environment {
        PYTHON_CMD = 'py'
        UV_CMD = 'uv'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                echo " Code récupéré depuis GitHub"
            }
        }

        stage('Setup Python') {
            steps {
                script {
                    def pythonVersion = bat(script: "${env.PYTHON_CMD} --version", returnStdout: true).trim()
                    echo " Version Python : ${pythonVersion}"
                }
            }
        }

        stage('Install Dependencies') {
            steps {
                script {
                    bat "${env.PYTHON_CMD} -m pip install uv"
                    bat "${env.UV_CMD} sync"
                    echo " Dépendances installées"
                }
            }
        }

        stage('Run Tests') {
            steps {
                script {
                    bat "${env.UV_CMD} run pytest --junitxml=test-results.xml"
                    echo " Tests passés"
                }
            }
            post {
                always {
                    junit 'test-results.xml'
                }
            }
        }

        stage('Build Docker Images') {
            steps {
                script {
                    bat "docker build -t dependency-sentinel-gateway:${env.BUILD_ID} -f services/gateway/Dockerfile ."
                    echo " Image Gateway construite"

                    bat "docker build -t dependency-sentinel-scanner:${env.BUILD_ID} -f services/repository_scanner_service/Dockerfile ."
                    echo " Image Scanner construite"
                }
            }
        }
    }

    post {
        success {
            echo " Pipeline terminé avec succès !"
            echo " Images créées :"
            echo "  - dependency-sentinel-gateway:${env.BUILD_ID}"
            echo "  - dependency-sentinel-scanner:${env.BUILD_ID}"
        }
        failure {
            echo " Le pipeline a échoué. Vérifie les logs."
        }
    }
}