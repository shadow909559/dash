#!/bin/bash
# DASH Website Deploy Script
# Builds the website, uploads to S3, and creates/updates CloudFront distribution
set -euo pipefail

BUCKET="dash-web-2026-909559"
REGION="ap-south-1"
S3_WEBSITE="http://${BUCKET}.s3-website.${REGION}.amazonaws.com"
S3_DIRECT="https://${BUCKET}.s3.${REGION}.amazonaws.com"
DIST_DIR="dist"

echo "🔧 Building DASH website..."
npm run build

if [ ! -d "$DIST_DIR" ]; then
  echo "❌ Build failed - dist/ not found"
  exit 1
fi

echo "📤 Uploading to S3..."
aws s3 sync "$DIST_DIR" "s3://${BUCKET}" \
  --delete \
  --cache-control "public, max-age=31536000, immutable" \
  --exclude "index.html" \
  --exclude "*.html"

# Upload HTML files with no-cache
aws s3 sync "$DIST_DIR" "s3://${BUCKET}" \
  --exclude "*" \
  --include "*.html" \
  --cache-control "no-cache, no-store, must-revalidate"

echo "🌐 S3 website: ${S3_WEBSITE}"
echo "🔒 S3 HTTPS:   ${S3_DIRECT}/index.html"

# Check if CloudFront distribution exists
EXISTING=$(aws cloudfront list-distributions --query "DistributionList.Items[?Comment=='DASH Website - HTTPS via CloudFront'].Id" --output text 2>/dev/null || echo "NONE")

if [ "$EXISTING" = "NONE" ] || [ -z "$EXISTING" ]; then
  echo ""
  echo "📡 Creating CloudFront distribution..."
  RESULT=$(aws cloudfront create-distribution --distribution-config file://cloudfront-config.json 2>&1) || {
    echo ""
    echo "⚠️  CloudFront creation failed."
    echo "   This usually means the AWS account needs verification."
    echo ""
    echo "   To fix:"
    echo "   1. Go to https://console.aws.amazon.com/support/home#/"
    echo "   2. Click 'Account support' or 'Service limit increase'"
    echo "   3. Request CloudFront distribution creation"
    echo "   4. Once approved, run this script again"
    echo ""
    echo "   The website is still accessible at:"
    echo "   HTTP:  ${S3_WEBSITE}"
    echo "   HTTPS: ${S3_DIRECT}/index.html"
    exit 0
  }

  DIST_ID=$(echo "$RESULT" | grep -o '"Id": "[^"]*"' | head -1 | cut -d'"' -f4)
  DIST_DOMAIN=$(echo "$RESULT" | grep -o '"DomainName": "[^"]*"' | head -1 | cut -d'"' -f4)
  echo "✅ CloudFront distribution created!"
  echo "   ID:     ${DIST_ID}"
  echo "   Domain: https://${DIST_DOMAIN}"
  echo ""
  echo "⏳ Distribution takes 15-30 minutes to deploy."
  echo "   Check status: aws cloudfront get-distribution --id ${DIST_ID} --query 'Distribution.Status'"
else
  echo ""
  echo "📡 CloudFront distribution exists: ${EXISTING}"
  echo "🔄 Creating invalidation..."
  aws cloudfront create-invalidation --distribution-id "$EXISTING" --paths "/*" --query "Invalidation.{Id:Id,Status:Status}" --output table
  echo "✅ Invalidation submitted. Changes propagate in 5-15 minutes."
fi

echo ""
echo "🎉 Deploy complete!"
echo "   HTTP:  ${S3_WEBSITE}"
echo "   HTTPS: ${S3_DIRECT}/index.html"
