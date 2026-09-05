# DASH — AWS Free Tier Setup Guide

## Overview

DASH uses these AWS **Always Free** services (costs $0 forever):

| Service | What DASH Uses It For | Free Limit |
|---------|----------------------|------------|
| **DynamoDB** | Device states, config storage | 25 GB + 25 WCU + 25 RCU |
| **S3** | APK distribution, config backup | 5 GB + 20K GET + 2K PUT |
| **SNS** | Push notifications to Android | 1M publishes + 100K HTTPS |
| **SQS** | Message queue Android↔PC↔Cloud | 1M requests/month |
| **CloudFront** | CDN for web app + static assets | 1 TB transfer + 10M requests |
| **Cognito** | User authentication | 50K MAU |
| **CloudWatch** | Monitoring + billing alerts | 10 metrics + 10 alarms + 5 GB logs |
| **CloudTrail** | Audit log of API calls | 1 trail free |
| **Systems Manager** | Manage EC2 remotely + Parameter Store | Free features |
| **Lambda** | Serverless cloud relay (future) | 1M requests + 400K GB-sec |

---

## STEP 1: Log in as Root

1. Go to **https://aws.amazon.com/console**
2. Click **"Sign In to the Console"**
3. Select **"Root user"** and enter your email: *(the one you used to create the account)*
4. Complete MFA if prompted

---

## STEP 2: Switch to us-east-1 (N. Virginia) Region

Most free-tier services are available globally, but we'll create resources in **ap-south-1** (Mumbai) since your EC2 is there.

1. In the top-right corner, click the **region dropdown**
2. Select **Asia Pacific (Mumbai) ap-south-1**

---

## STEP 3: Create the IAM Policy

1. In the search bar, type **"IAM"** and click **IAM** (under Services)
2. In the left sidebar, click **Policies**
3. Click **Create policy**
4. Click the **JSON** tab
5. **Delete everything** in the text box and paste this:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "DynamoDBFullAccess",
            "Effect": "Allow",
            "Action": [
                "dynamodb:CreateTable",
                "dynamodb:DescribeTable",
                "dynamodb:ListTables",
                "dynamodb:PutItem",
                "dynamodb:GetItem",
                "dynamodb:UpdateItem",
                "dynamodb:DeleteItem",
                "dynamodb:Query",
                "dynamodb:Scan",
                "dynamodb:BatchWriteItem",
                "dynamodb:BatchGetItem",
                "dynamodb:DescribeTimeToLive",
                "dynamodb:UpdateTimeToLive"
            ],
            "Resource": "arn:aws:dynamodb:ap-south-1:752651103716:table/dash-*"
        },
        {
            "Sid": "S3FullAccess",
            "Effect": "Allow",
            "Action": [
                "s3:CreateBucket",
                "s3:ListBucket",
                "s3:GetBucketLocation",
                "s3:GetObject",
                "s3:PutObject",
                "s3:DeleteObject",
                "s3:DeleteBucket",
                "s3:PutBucketPolicy",
                "s3:GetBucketPolicy",
                "s3:PutBucketPublicAccessBlock",
                "s3:GetBucketPublicAccessBlock"
            ],
            "Resource": [
                "arn:aws:s3:::dash-*",
                "arn:aws:s3:::dash-*/*"
            ]
        },
        {
            "Sid": "SNSFullAccess",
            "Effect": "Allow",
            "Action": [
                "sns:CreateTopic",
                "sns:DeleteTopic",
                "sns:Subscribe",
                "sns:Unsubscribe",
                "sns:Publish",
                "sns:ListTopics",
                "sns:ListSubscriptionsByTopic",
                "sns:SetTopicAttributes",
                "sns:GetTopicAttributes"
            ],
            "Resource": "arn:aws:sns:ap-south-1:752651103716:dash-*"
        },
        {
            "Sid": "SQSFullAccess",
            "Effect": "Allow",
            "Action": [
                "sqs:CreateQueue",
                "sqs:DeleteQueue",
                "sqs:SendMessage",
                "sqs:ReceiveMessage",
                "sqs:DeleteMessage",
                "sqs:GetQueueUrl",
                "sqs:ListQueues",
                "sqs:SetQueueAttributes",
                "sqs:GetQueueAttributes",
                "sqs:PurgeQueue"
            ],
            "Resource": "arn:aws:sqs:ap-south-1:752651103716:dash-*"
        },
        {
            "Sid": "LambdaFullAccess",
            "Effect": "Allow",
            "Action": [
                "lambda:CreateFunction",
                "lambda:GetFunction",
                "lambda:GetFunctionConfiguration",
                "lambda:ListFunctions",
                "lambda:UpdateFunctionCode",
                "lambda:UpdateFunctionConfiguration",
                "lambda:DeleteFunction",
                "lambda:InvokeFunction",
                "lambda:AddPermission",
                "lambda:RemovePermission",
                "lambda:CreateEventSourceMapping",
                "lambda:DeleteEventSourceMapping",
                "lambda:ListEventSourceMappings"
            ],
            "Resource": "arn:aws:lambda:ap-south-1:752651103716:function:dash-*"
        },
        {
            "Sid": "CloudWatchFullAccess",
            "Effect": "Allow",
            "Action": [
                "cloudwatch:PutMetricData",
                "cloudwatch:GetMetricData",
                "cloudwatch:GetMetricStatistics",
                "cloudwatch:ListMetrics",
                "cloudwatch:PutMetricAlarm",
                "cloudwatch:DescribeAlarms",
                "cloudwatch:DeleteAlarms",
                "cloudwatch:EnableAlarmActions",
                "cloudwatch:DisableAlarmActions"
            ],
            "Resource": "*"
        },
        {
            "Sid": "CloudWatchLogsFullAccess",
            "Effect": "Allow",
            "Action": [
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents",
                "logs:DescribeLogGroups",
                "logs:DescribeLogStreams",
                "logs:GetLogEvents",
                "logs:DeleteLogGroup"
            ],
            "Resource": "arn:aws:logs:ap-south-1:752651103716:*"
        },
        {
            "Sid": "IAMRoleForLambda",
            "Effect": "Allow",
            "Action": [
                "iam:CreateRole",
                "iam:DeleteRole",
                "iam:GetRole",
                "iam:PassRole",
                "iam:AttachRolePolicy",
                "iam:DetachRolePolicy",
                "iam:PutRolePolicy",
                "iam:GetRolePolicy",
                "iam:ListRolePolicies",
                "iam:ListAttachedRolePolicies"
            ],
            "Resource": "arn:aws:iam::752651103716:role/dash-*"
        },
        {
            "Sid": "CloudTrailAccess",
            "Effect": "Allow",
            "Action": [
                "cloudtrail:CreateTrail",
                "cloudtrail:DeleteTrail",
                "cloudtrail:DescribeTrails",
                "cloudtrail:StopLogging",
                "cloudtrail:StartLogging",
                "cloudtrail:GetTrailStatus"
            ],
            "Resource": "arn:aws:cloudtrail:ap-south-1:752651103716:trail/dash-*"
        },
        {
            "Sid": "SSMParameterStore",
            "Effect": "Allow",
            "Action": [
                "ssm:PutParameter",
                "ssm:GetParameter",
                "ssm:GetParameters",
                "ssm:DeleteParameter",
                "ssm:GetParametersByPath"
            ],
            "Resource": "arn:aws:ssm:ap-south-1:752651103716:parameter/dash/*"
        },
        {
            "Sid": "EC2ExistingAccess",
            "Effect": "Allow",
            "Action": [
                "ec2:DescribeInstances",
                "ec2:StartInstances",
                "ec2:StopInstances",
                "ec2:DescribeInstanceStatus",
                "ec2:DescribeTags"
            ],
            "Resource": "arn:aws:ec2:ap-south-1:752651103716:instance/*"
        }
    ]
}
```

6. Click **"Next"**
7. **Policy name**: type `DASH-FreeTier-FullAccess`
8. **Description**: `Full access to all AWS free forever services for DASH`
9. Click **"Create policy"**

---

## STEP 4: Attach the Policy to dash-storage User

1. In the left sidebar, click **Users**
2. Click **dash-storage**
3. Click **Permissions** tab
4. Click **Add permissions** → **Attach policies directly**
5. In the search box, type `DASH-FreeTier`
6. Check the box next to **DASH-FreeTier-FullAccess**
7. Click **Next** → **Add permissions**
8. Also check if there's an existing **AmazonEC2FullAccess** or similar policy attached. If not, attach it too.

---

## STEP 5: Create DynamoDB Tables

Still in the AWS Console:

1. Search for **"DynamoDB"** and open it
2. Click **Create table**
3. **Table name**: `dash-device-states`
4. **Partition key**: `device_id` (String)
5. Click **Create table**
6. Wait for status to become **Active**
7. Click **Create table** again
8. **Table name**: `dash-config`
9. **Partition key**: `key` (String)
10. Click **Create table**
11. Click **Create table** again
12. **Table name**: `dash-sync-log`
13. **Partition key**: `id` (String)
14. Click **Create table**

---

## STEP 6: Create S3 Bucket

1. Search for **"S3"** and open it
2. Click **Create bucket**
3. **Bucket name**: `dash-storage-752651103716` (must be globally unique)
4. **Region**: Asia Pacific (Mumbai) ap-south-1
5. **Block Public Access**: Keep all blocks ON (for security)
6. Scroll down, click **Create bucket**
7. Click on the bucket name to open it
8. Go to **Properties** tab
9. Under **Default encryption**, verify it says "Server-side encryption with Amazon S3 managed keys (SSE-S3)" — this is free
10. Go to **Permissions** tab
11. Under **Bucket policy**, click **Edit** and paste:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowDASHBackendAccess",
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::752651103716:user/dash-storage"
            },
            "Action": [
                "s3:GetObject",
                "s3:PutObject",
                "s3:ListBucket",
                "s3:DeleteObject"
            ],
            "Resource": [
                "arn:aws:s3:::dash-storage-752651103716",
                "arn:aws:s3:::dash-storage-752651103716/*"
            ]
        }
    ]
}
```

12. Click **Save changes**

---

## STEP 7: Create SNS Topic for Notifications

1. Search for **"Simple Notification Service (SNS)"** and open it
2. Make sure you're in **ap-south-1** region
3. Click **Topics** in the left sidebar
4. Click **Create topic**
5. Type: **Standard** (not FIFO — FIFO costs money)
6. **Name**: `dash-notifications`
7. Click **Create topic**
8. Copy the **ARN** (looks like `arn:aws:sns:ap-south-1:752651103716:dash-notifications`)
9. You'll need this ARN in the backend config

---

## STEP 8: Create SQS Queue

1. Search for **"Simple Queue Service (SQS)"** and open it
2. Click **Create queue**
3. **Type**: Standard (not FIFO)
4. **Name**: `dash-commands`
5. Keep all other settings as default
6. Click **Create queue**
7. Copy the **URL** from the queue details page
8. Create another queue:
   - **Name**: `dash-notifications-queue`
   - **Type**: Standard
   - Click **Create queue**

---

## STEP 9: Create CloudWatch Budget Alert

1. Search for **"Budgets"** or go to: **https://console.aws.amazon.com/costmanagement/home**
2. Click **Budgets** in the left sidebar
3. Click **Create budget**
4. Select **Cost budget** → Next
5. **Budget name**: `DASH-FreeTier-Alert`
6. **Budgeted amount**: `$1.00`
7. **Budget type**: Monthly
8. Click **Next**
9. Under **Alert conditions**:
   - **Threshold**: 100% of budgeted amount
   - **Email recipients**: your email address
10. Click **Next** → **Create budget**

This alerts you if you ever go over $1/month.

---

## STEP 10: Create CloudWatch Alarms for EC2

1. Search for **"CloudWatch"** and open it
2. Click **Alarms** → **All alarms** → **Create alarm**
3. Click **Select metric** → **EC2** → **Per-Instance Metrics**
4. Select **CPUUtilization** for your instance
5. Click **Select metric**
6. **Threshold type**: Static
7. **Whenever CPUUtilization is...**: Greater than 90%
8. For **1** consecutive datapoint(s)
9. Click **Next**
10. **Alarm name**: `DASH-High-CPU`
11. Click **Next** → **Create alarm**

---

## STEP 11: Enable CloudTrail (Optional but Free)

1. Search for **"CloudTrail"** and open it
2. Click **Trails** → **Create trail**
3. **Trail name**: `dash-audit-trail`
4. **S3 bucket**: Select the `dash-storage-752651103716` bucket you created
5. **Log file SSE-KMS**: Disabled (saves money)
6. **Log file validation**: Enabled
7. **CloudWatch Logs**: Enable
8. **Log group**: `/aws/cloudtrail/dash`
9. Click **Next**
10. **Events**: Read-only (free) + Write-only (free)
11. **Management events**: All
12. Click **Next** → **Create trail**

---

## STEP 12: Create SSM Parameters for Config

1. Search for **"Systems Manager"** and open it
2. In the left sidebar, expand **Application Management** → **Parameter Store**
3. Click **Create parameter**
4. **Name**: `/dash/config/supabase_url`
5. **Type**: String
6. **Value**: *(your Supabase URL from the .env file)*
7. Click **Create parameter**
8. Create another:
   - **Name**: `/dash/config/supabase_key`
   - **Type**: SecureString
   - **Value**: *(your Supabase anon key)*
9. Create another:
   - **Name**: `/dash/config/ec2_instance_id`
   - **Type**: String
   - **Value**: `i-0546d2c1b0c7346a5`
10. Create another:
    - **Name**: `/dash/config/ec2_region`
    - **Type**: String
    - **Value**: `ap-south-1`

---

## STEP 13: Verify Everything Works

Open a terminal and run these commands (one at a time):

```bash
# Test DynamoDB
aws dynamodb list-tables --region ap-south-1

# Test S3
aws s3 ls | grep dash

# Test SNS
aws sns list-topics --region ap-south-1

# Test SQS
aws sqs list-queues --region ap-south-1

# Test CloudWatch
aws cloudwatch list-metrics --region ap-south-1 --namespace "DASH"

# Test SSM
aws ssm get-parameter --name "/dash/config/ec2_instance_id" --region ap-south-1
```

All commands should return data without AccessDenied errors.

---

## STEP 14: Set Up Vercel Deployment (Free Tier)

1. Go to **https://vercel.com**
2. Sign up with GitHub (same account as your repo)
3. Import the `dash` repository
4. **Framework Preset**: Vite
5. **Root Directory**: `apps/desktop`
6. Click **Deploy**
7. It should deploy at: `https://dash-v1.vercel.app`

---

## What Each Service Does for DASH

### DynamoDB (25 GB free)
```
Android App → Cloud Relay → DynamoDB stores:
  - Device states (PC online/offline, IP, MAC)
  - Config (settings, preferences)
  - Sync log (what was synced when)
```

### S3 (5 GB free)
```
DASH Backend → S3 stores:
  - Android APK files (auto-update)
  - Config backups
  - Log archives
  - Obsidian vault exports
```

### SNS (1M publishes free)
```
DASH Backend → SNS → Android gets:
  - "PC is coming online"
  - "WoL packet sent"
  - "EC2 started successfully"
  - "New Ollama model available"
```

### SQS (1M requests free)
```
Android → SQS ← Backend:
  - Command queue (Android sends commands)
  - Notification queue (Backend sends responses)
  - Works even when PC is off (if EC2 is running)
```

### CloudWatch (10 metrics free)
```
DASH Backend → CloudWatch tracks:
  - Request count per minute
  - Error rate
  - Response time
  - EC2 CPU utilization
  - Monthly cost estimate
```

---

## Cost Summary

| Service | Monthly Free Limit | DASH Expected Usage | Cost |
|---------|-------------------|--------------------|----|
| DynamoDB | 25 GB | ~1 MB | $0 |
| S3 | 5 GB | ~100 MB | $0 |
| SNS | 1M publishes | ~1,000 | $0 |
| SQS | 1M requests | ~10,000 | $0 |
| Lambda | 1M requests | ~10,000 | $0 |
| CloudWatch | 10 metrics | ~5 | $0 |
| Cognito | 50K users | 1 | $0 |
| CloudFront | 1 TB transfer | ~1 GB | $0 |
| **Total** | | | **$0** |

**Only EC2 costs money when running** ($0.0116/hr for t3.micro). All other services are ALWAYS FREE.
