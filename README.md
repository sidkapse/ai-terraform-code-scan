# AI Terraform Security Scanner


A professional CI/CD integration that combines **Terrascan**'s static analysis with **Amazon Bedrock (Claude 3.5)** for intelligent security insights.

## 🚀 Setup & Prerequisites

### 1. Local Requirements
- **Python 3.10+**
- **Terrascan CLI:** [Install guide](https://runterrascan.io/docs/install/)
- **AWS CLI:** Configured with access to Bedrock and S3.

### 2. Repository Setup
Place the following files in your repository root:
- `code-scanner.py`: The main execution logic.
- `requirements.txt`: Contains `boto3` and `click`.

### 3. CI/CD Environment
Add the following:
- `AWS_ROLE_ARN`: The IAM Role for the runner (must have Bedrock & S3 permissions). [NON-AWS-SERVICES]
- `SCAN_RESULTS_BUCKET`: The name of the S3 bucket to store reports.

## 🛠 Usage
The scanner runs automatically on every Pull Request. To run it manually:
```bash
pip install -r requirements.txt
python tf-code-scanner.py --bucket your-s3-bucket-name
Note: If bucket name is not provided than a file with current datetime will be saved at the present working directory.

## Usage To implement a professional security posture, you should avoid long-lived IAM Access Keys. Instead, use Identity Federation for external services (GitHub/GitLab) and Service Roles for AWS-native services.

1. GitHub Actions: OIDC (OpenID Connect)
GitHub Actions uses OIDC to request temporary credentials from AWS. This is the industry standard for security.

A. Create the OIDC Identity Provider In the AWS IAM Console:

Go to Identity Providers > Add provider.

Choose OpenID Connect.

Provider URL: https://token.actions.githubusercontent.com

Audience: sts.amazonaws.com

B. Define the Trust Policy Create a role with a trust policy that limits access to only your specific repository:

JSON
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::<ACCOUNT_ID>:oidc-provider/token.actions.githubusercontent.com"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "token.actions.githubusercontent.com:aud": "sts.amazonaws.com"
        },
        "StringLike": {
          "token.actions.githubusercontent.com:sub": "repo:<ORG>/<REPO>:*"
        }
      }
    }
  ]
}

2. GitLab CI/CD: OIDC Federation
GitLab functions similarly to GitHub but uses its own OIDC provider URL.

A. IAM Configuration 1. Provider URL: https://gitlab.com (or your self-hosted URL). 2. Audience: https://gitlab.com 3. Trust Policy: Use the sts:AssumeRoleWithWebIdentity action, filtering the sub claim by your GitLab project ID or group.

B. GitLab Workflow (.gitlab-ci.yml) You must define an id_token to pass to AWS:

variables:
  AWS_ROLE_ARN: arn:aws:iam::<ACCOUNT_ID>:role/GitLabScannerRole

scan-job:
  id_tokens:
    MY_OIDC_TOKEN:
      aud: https://gitlab.com
  script:
    - # Use AWS CLI to exchange MY_OIDC_TOKEN for temporary keys

3. AWS CodeBuild: Service Role (RBAC)
Since CodeBuild is internal to AWS, it uses a Service Role. There are no tokens to exchange; the permissions are attached directly to the role assumed by the CodeBuild project.

Trust Relationship: Must allow codebuild.amazonaws.com to sts:AssumeRole.

Assignment: Go to your CodeBuild project > Environment > Service Role and select the role you created.

4. Shared Least-Privilege Permissions
Regardless of the CI/CD service, attach this Inline Policy to the role to allow Bedrock and S3 access:

{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "BedrockInvoke",
      "Effect": "Allow",
      "Action": "bedrock:InvokeModel",
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-5-sonnet-20240620-v1:0"
    },
    {
      "Sid": "S3Upload",
      "Effect": "Allow",
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::<YOUR_BUCKET_NAME>/scans/*"
    }
  ]
}