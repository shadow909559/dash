# CloudFront HTTPS Setup for DASH Website

## Current Status

| Component | Status | URL |
|-----------|--------|-----|
| S3 Bucket | ✅ Live | `dash-web-2026-909559` |
| S3 Website (HTTP) | ✅ Working | http://dash-web-2026-909559.s3-website.ap-south-1.amazonaws.com |
| S3 HTTPS (direct) | ✅ Working | https://dash-web-2026-909559.s3.ap-south-1.amazonaws.com/index.html |
| CORS | ✅ Configured | `*` origins, GET/HEAD methods |
| Public Read | ✅ Enabled | All objects publicly accessible |
| CloudFront HTTPS | ⚠️ Blocked | AWS account verification required |

## Why CloudFront is Blocked

AWS requires account verification before creating CloudFront distributions. This is a standard restriction for new accounts. The `dash-storage` IAM user lacks CloudFront permissions.

## How to Enable CloudFront

### Step 1: Verify AWS Account
1. Go to [AWS Support Center](https://console.aws.amazon.com/support/home#/)
2. Sign in with the **root account** (not the dash-storage user)
3. If prompted, complete the account verification process
4. This may take 24-48 hours for new accounts

### Step 2: Add CloudFront Permissions to dash-storage
Create an IAM policy and attach it to the `dash-storage` user:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "CloudFrontFullAccess",
      "Effect": "Allow",
      "Action": [
        "cloudfront:CreateDistribution",
        "cloudfront:GetDistribution",
        "cloudfront:UpdateDistribution",
        "cloudfront:DeleteDistribution",
        "cloudfront:CreateInvalidation",
        "cloudfront:GetInvalidation",
        "cloudfront:ListDistributions",
        "cloudfront:TagResource"
      ],
      "Resource": "*"
    }
  ]
}
```

### Step 3: Create CloudFront Distribution
Once verified, run:
```bash
cd dash_web
bash deploy.sh
```

Or manually:
```bash
aws cloudfront create-distribution --distribution-config file://cloudfront-config.json
```

### Step 4: Verify
```bash
# Check distribution status (takes 15-30 minutes)
aws cloudfront get-distribution --id <DISTRIBUTION_ID> --query 'Distribution.Status'

# Test HTTPS access
curl -sI https://<DISTRIBUTION_DOMAIN>/
```

## What CloudFront Provides

| Feature | Without CloudFront | With CloudFront |
|---------|-------------------|-----------------|
| HTTPS | ❌ HTTP only (website endpoint) | ✅ Full HTTPS with free SSL |
| HTTP/2 | ❌ | ✅ Multiplexed connections |
| HTTP/3 | ❌ | ✅ QUIC protocol |
| Compression | ❌ | ✅ Auto gzip/brotli |
| Global CDN | ❌ Single region | ✅ 400+ edge locations |
| DDoS Protection | ❌ | ✅ AWS Shield Standard |
| Cache Invalidation | ❌ | ✅ Instant invalidation |

## Deploy Script

`deploy.sh` automates the full pipeline:
1. `npm run build` — builds the website
2. `aws s3 sync` — uploads to S3 with cache headers
3. `aws cloudfront create-distribution` — creates or invalidates CloudFront

## Files Created

- `deploy.sh` — Automated deploy script
- `cloudfront-config.json` — CloudFront distribution configuration
- `CLOUDFRONT_SETUP.md` — This file
