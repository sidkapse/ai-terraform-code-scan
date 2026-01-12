import os
import sys
import json
import subprocess
import boto3
import click
from datetime import datetime

# ANSI Color Codes for Pipeline Logs
RED = "\033[91m"
GREEN = "\033[92m"
BOLD = "\033[1m"
RESET = "\033[0m"

def run_terrascan():
    """Executes terrascan locally and returns the JSON output."""
    try:
        # Run terrascan on the current directory and output as JSON
        result = subprocess.run(
            ["terrascan", "scan", "-o", "json"], 
            capture_output=True, text=True, check=False
        )
        return json.loads(result.stdout)
    except Exception as e:
        print(f"{RED}Error running Terrascan: {e}{RESET}")
        sys.exit(1)

def get_ai_review(findings):
    """Sends findings to Bedrock for a professional AI summary using Amazon Nova."""
    bedrock = boto3.client(service_name='bedrock-runtime')
    
    # Extract only relevant parts to reduce token count
    scan_summary = findings.get("scan_summary", {})
    violations = findings.get("violations", [])
    
    # Limit violations to first 10 to avoid exceeding token limit
    if violations and len(violations) > 10:
        violations = violations[:10]
    
    condensed_findings = {
        "scan_summary": scan_summary,
        "violations": violations if violations else "No violations found"
    }
    
    # Professional System Prompt with condensed findings
    prompt = (
        "You are a Senior Cloud Security Architect. Review the following Terrascan findings "
        "and provide a concise, executive summary. Group issues by severity (High, Medium, Low). "
        "Highlight the single most critical fix needed. Format the output in clean Markdown.\n\n"
        f"FINDINGS:\n{json.dumps(condensed_findings, indent=2)}"
    )

    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": prompt}]}]
    })

    try:
        response = bedrock.invoke_model(
            modelId='arn:aws:bedrock:ap-southeast-1:944101541587:inference-profile/apac.amazon.nova-micro-v1:0',
            body=body
        )
        
        response_body = json.loads(response.get('body').read())
        print(f"{BOLD}AI Response:{RESET} {json.dumps(response_body, indent=2)}")
        
        # Handle different response formats from Amazon Nova
        if 'content' in response_body:
            return response_body['content'][0]['text']
        elif 'output' in response_body:
            return response_body['output'][0]['text']
        else:
            # If format is unexpected, return the full response as string
            return json.dumps(response_body, indent=2)
    except Exception as e:
        print(f"{RED}Error getting AI review: {e}{RESET}")
        return "AI review generation failed."

@click.command()
@click.option('--bucket', required=False, help='S3 Bucket name for results')
def main(bucket):
    # 1. Run Terrascan
    print(f"{BOLD}Step 1: Running local Terrascan scan...{RESET}")
    scan_results = run_terrascan()
    
    # 2. Check if valid terraform config files are present
    results = scan_results.get("results", {})
    scan_errors = results.get("scan_errors", [])
    scan_summary = results.get("scan_summary", {})
    violated_policies = scan_summary.get("violated_policies", 0)
    
    # Check if valid terraform code repository was passed
    terraform_error = None
    for error in scan_errors:
        if error.get("iac_type") == "terraform":
            terraform_error = error.get("errMsg")
            break
    
    if terraform_error:
        print(f"{RED}{BOLD}✖ ERROR: {terraform_error}{RESET}")
        sys.exit(1)
    
    # 3. If terraform files are present, get AI Summary
    print(f"{BOLD}Step 2: Generating AI Security Review...{RESET}")
    ai_summary = get_ai_review(scan_results)
    
    # 4. Save AI Summary to markdown file
    now = datetime.now()
    md_file_name = f"review_{now.strftime('%Y%m%d_%H%M%S')}.md"
    
    if bucket:
        # Save to S3
        s3 = boto3.client('s3')
        folder_path = now.strftime("reviews/%Y/%m/%d")
        s3_key = f"{folder_path}/{md_file_name}"
        
        s3.put_object(Bucket=bucket, Key=s3_key, Body=ai_summary)
        print(f"{GREEN}✓ AI Review saved to s3://{bucket}/{s3_key}{RESET}")
    else:
        # Save to local current working directory
        md_file_path = os.path.join(os.getcwd(), md_file_name)
        
        with open(md_file_path, 'w') as f:
            f.write(ai_summary)
        print(f"{GREEN}✓ AI Review saved to {md_file_path}{RESET}")
    
    # 5. Save scan results (JSON)
    file_name = f"scan_{now.strftime('%Y%m%d_%H%M%S')}.json"
    json_output = json.dumps(scan_results, indent=2)

    # 6. Final Output & Exit Logic
    print(f"\n{BOLD}--- FINAL REVIEW ---{RESET}")
    print(ai_summary)
    
    if violated_policies > 0:
        print(f"{RED}{BOLD}✖ FAIL: Found {violated_policies} policy violation(s).{RESET}")
        if bucket:
            # Save JSON to S3
            s3 = boto3.client('s3')
            folder_path = now.strftime("scans/%Y/%m/%d")
            s3_key = f"{folder_path}/{file_name}"
            
            s3.put_object(Bucket=bucket, Key=s3_key, Body=json_output)
            print(f"{GREEN}✓ Scan results saved to s3://{bucket}/{s3_key}{RESET}")
        else:
            # Save JSON to local current working directory
            file_path = os.path.join(os.getcwd(), file_name)
            
            with open(file_path, 'w') as f:
                f.write(json_output)
            print(f"{GREEN}✓ Scan results saved to {file_path}{RESET}")
        sys.exit(1)
    else:
        print(f"{GREEN}{BOLD}✔ PASS: No vulnerabilities detected in valid Terraform code.{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()