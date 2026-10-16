// ClinEval-CI pipeline: checkout -> build -> test -> eval gate -> deploy (local or Azure VM) -> smoke test
pipeline {
  agent any

  parameters {
    choice(name: 'DEPLOY_TARGET', choices: ['local', 'azure'], description: 'Where to deploy after the gate passes')
  }

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '15'))
  }

  triggers {
    pollSCM('H/2 * * * *')
  }

  environment {
    VM_USER  = 'azureuser'
    SSH_OPTS = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
    LIVE_DIR = '/var/jenkins_home/clineval-live'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
        sh 'git log -1 --pretty=format:"%h %an: %s"'
      }
    }

    stage('Build') {
      steps {
        sh '''
          python3 -m venv venv
          venv/bin/pip install -q --upgrade pip
          venv/bin/pip install -q -r requirements.txt
        '''
      }
    }

    stage('Unit Tests') {
      steps {
        sh 'venv/bin/pytest -q'
      }
    }

    stage('Eval Gate') {
      steps {
        sh 'venv/bin/python -m clineval.cli lint'
        sh 'venv/bin/python -m clineval.cli gate'
      }
      post {
        always {
          archiveArtifacts artifacts: 'gate-report.md,gate-junit.xml,gate-result.json', allowEmptyArchive: true
          junit testResults: 'gate-junit.xml', allowEmptyResults: true
        }
      }
    }

    stage('Deploy (local)') {
      when { expression { params.DEPLOY_TARGET == 'local' } }
      steps {
        withEnv(['JENKINS_NODE_COOKIE=dontKillMe']) {
          sh '''
            set -e
            mkdir -p "$LIVE_DIR"
            rsync -a --delete --exclude '.git' --exclude 'venv' --exclude 'data' --exclude '__pycache__' \
              --exclude 'terraform' --exclude 'jenkins' --exclude 'app.pid' --exclude 'app.log' ./ "$LIVE_DIR"/
            cd "$LIVE_DIR"
            [ -d venv ] || python3 -m venv venv
            venv/bin/pip install -q -r requirements.txt
            if [ -f app.pid ]; then kill "$(cat app.pid)" 2>/dev/null || true; sleep 1; fi
            setsid nohup venv/bin/uvicorn clineval.api:app --host 0.0.0.0 --port 8000 > app.log 2>&1 < /dev/null &
            echo $! > app.pid
            echo "App started with pid $(cat app.pid)"
          '''
        }
      }
    }

    stage('Deploy to Azure VM') {
      when { expression { params.DEPLOY_TARGET == 'azure' } }
      steps {
        withCredentials([string(credentialsId: 'azure-vm-ip', variable: 'VM_IP')]) {
          sshagent(credentials: ['azure-vm-ssh']) {
            sh '''
              rsync -az --delete -e "ssh $SSH_OPTS" \
                --exclude '.git' --exclude 'venv' --exclude 'data' \
                --exclude '__pycache__' --exclude 'terraform' --exclude 'jenkins' \
                ./ ${VM_USER}@${VM_IP}:/opt/clineval/
              ssh $SSH_OPTS ${VM_USER}@${VM_IP} 'bash /opt/clineval/deploy/remote_deploy.sh'
            '''
          }
        }
      }
    }

    stage('Smoke Test') {
      steps {
        script {
          if (params.DEPLOY_TARGET == 'local') {
            sh '''
              sleep 4
              curl -fsS http://localhost:8000/api/health
              echo
              curl -fsS -o /dev/null -w "Dashboard HTTP %{http_code}\\n" http://localhost:8000/app
            '''
          } else {
            withCredentials([string(credentialsId: 'azure-vm-ip', variable: 'VM_IP')]) {
              sh '''
                sleep 3
                curl -fsS http://${VM_IP}/api/health
                echo
                curl -fsS -o /dev/null -w "Dashboard HTTP %{http_code}\\n" http://${VM_IP}/app
              '''
            }
          }
        }
      }
    }
  }

  post {
    success { echo "Deployed successfully (${params.DEPLOY_TARGET})." }
    failure { echo 'Pipeline failed. Nothing new was deployed.' }
  }
}