// ClinEval-CI pipeline: checkout -> build -> test -> eval gate -> deploy to Azure VM -> smoke test
pipeline {
  agent any

  options {
    timestamps()
    disableConcurrentBuilds()
    buildDiscarder(logRotator(numToKeepStr: '15'))
  }

  // Poll SCM every ~2 minutes. (Optionally add githubPush() and configure a GitHub webhook.)
  triggers {
    pollSCM('H/2 * * * *')
  }

  environment {
    VM_USER  = 'azureuser'
    SSH_OPTS = '-o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'
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

    // The CI/CD safety net: a regressed agent fails here (exit code 1) and is never deployed.
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

    stage('Deploy to Azure VM') {
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
        withCredentials([string(credentialsId: 'azure-vm-ip', variable: 'VM_IP')]) {
          sh '''
            sleep 3
            curl -fsS http://${VM_IP}/api/health
            echo
            curl -fsS -o /dev/null -w "Dashboard HTTP %{http_code}\\n" http://${VM_IP}/
          '''
        }
      }
    }
  }

  post {
    success { echo 'Deployed successfully. App is live on the Azure VM.' }
    failure { echo 'Pipeline failed - nothing was deployed (or deployment was rolled back by the health check).' }
  }
}
