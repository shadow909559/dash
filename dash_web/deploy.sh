#!/bin/bash
# DASH Website Deployment Script
# Deploys the built website to AWS S3 and invalidates CloudFront cache.
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - Node.js installed
#   - npm installed
#
# Environment variables (optional, have defaults):
#   AWS_S3_BUCKET        - S3 bucket name (default: dash-web-2026-909559)
#   AWS_REGION           - AWS region (default: ap-south-1)
#   AWS_CF_DISTRIBUTION  - CloudFront distribution ID (optional)

set -euo pipefail

BUCKET="${AWS_S3_BUCKET:-dash-web-2026-909559}"
REGION="${AWS_REGION:-ap-south-1}"
CF_DIST="${AWS_CF_DISTRIBUTION:-}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== DASH Website Deployment ==="
echo "Bucket: $BUCKET"
echo "Region: $REGION"

# Step 1: Install dependencies
echo ""
echo ">>> Step 1: Installing dependencies..."
cd "$SCRIPT_DIR"
npm install --silent

# Step 2: TypeScript check
echo ">>> Step 2: TypeScript check..."
npx tsc -b

# Step 3: Build
echo ">>> Step 3: Building production bundle..."
npx vite build

# Step 4: Verify build
echo ">>> Step 4: Verifying build..."
if [ ! -f dist/index.html ]; then
  echo "ERROR: dist/index.html not found"
  exit 1
fi
echo "Build verified: $(ls dist/ | wc -l) files"

# Step 5: Upload to S3
echo ">>> Step 5: Uploading to S3..."
aws s3 sync dist/ "s3://$BUCKET" --region "$REGION" --delete
echo "Upload complete"

# Step 6: Invalidate CloudFront (if configured)
if [ -n "$CF_DIST" ]; then
  echo ">>> Step 6: Invalidating CloudFront distribution $CF_DIST..."
  aws cloudfront create-invalidation \
    --distribution-id "$CF_DIST" \
    --paths "/index.html" "/assets/*" "/*"
  echo "Invalidation submitted"
else
  echo ">>> Step 6: Skipped (no CloudFront distribution ID configured)"
fi

# Step 7: Report
WEBSITE_URL="http://$BUCKET.s3-website.$REGION.amazonaws.com"
S3_URL="https://$BUCKET.s3.$REGION.amazonaws.com"
echo ""
echo "=== Deployment Complete ==="
echo "S3 Direct:  $S3_URL/index.html"
echo "Website:    $WEBSITE_URL"
if [ -n "$CF_DIST" ]; then
  CF_DOMAIN=$(aws cloudfront get-distribution --id "$CF_DIST" --query "Distribution.DomainName" --output text 2>/dev/null || echo "unknown")
  echo "CloudFront: https://$CF_DOMAIN"
fi
echo ""
echo "Note: CloudFront requires account verification for new distributions."
echo "      Visit https://console.aws.amazon.com/support/ to verify your account."
