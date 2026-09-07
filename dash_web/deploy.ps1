# DASH Website Deployment Script (PowerShell)
# Deploys the built website to AWS S3 and invalidates CloudFront cache.
#
# Prerequisites:
#   - AWS CLI configured with appropriate permissions
#   - Node.js installed
#   - npm installed
#
# Environment variables (optional, have defaults):
#   $env:AWS_S3_BUCKET        - S3 bucket name (default: dash-web-2026-909559)
#   $env:AWS_REGION           - AWS region (default: ap-south-1)
#   $env:AWS_CF_DISTRIBUTION  - CloudFront distribution ID (optional)

$ErrorActionPreference = "Stop"

$Bucket = if ($env:AWS_S3_BUCKET) { $env:AWS_S3_BUCKET } else { "dash-web-2026-909559" }
$Region = if ($env:AWS_REGION) { $env:AWS_REGION } else { "ap-south-1" }
$CfDist = if ($env:AWS_CF_DISTRIBUTION) { $env:AWS_CF_DISTRIBUTION } else { "" }

Write-Host "=== DASH Website Deployment ===" -ForegroundColor Cyan
Write-Host "Bucket: $Bucket"
Write-Host "Region: $Region"

# Step 1: Install dependencies
Write-Host "`n>>> Step 1: Installing dependencies..."
npm install --silent

# Step 2: TypeScript check
Write-Host ">>> Step 2: TypeScript check..."
npx tsc -b

# Step 3: Build
Write-Host ">>> Step 3: Building production bundle..."
npx vite build

# Step 4: Verify build
Write-Host ">>> Step 4: Verifying build..."
if (-not (Test-Path "dist\index.html")) {
    Write-Host "ERROR: dist\index.html not found" -ForegroundColor Red
    exit 1
}
$FileCount = (Get-ChildItem dist -Recurse -File).Count
Write-Host "Build verified: $FileCount files"

# Step 5: Upload to S3
Write-Host ">>> Step 5: Uploading to S3..."
aws s3 sync dist/ "s3://$Bucket" --region $Region --delete
Write-Host "Upload complete" -ForegroundColor Green

# Step 6: Invalidate CloudFront (if configured)
if ($CfDist) {
    Write-Host ">>> Step 6: Invalidating CloudFront distribution $CfDist..."
    aws cloudfront create-invalidation --distribution-id $CfDist --paths "/index.html" "/assets/*" "/*"
    Write-Host "Invalidation submitted" -ForegroundColor Green
} else {
    Write-Host ">>> Step 6: Skipped (no CloudFront distribution ID configured)"
}

# Step 7: Report
$WebsiteUrl = "http://$Bucket.s3-website.$Region.amazonaws.com"
$S3Url = "https://$Bucket.s3.$Region.amazonaws.com"
Write-Host "`n=== Deployment Complete ===" -ForegroundColor Cyan
Write-Host "S3 Direct:  $S3Url/index.html"
Write-Host "Website:    $WebsiteUrl"
if ($CfDist) {
    $CfDomain = aws cloudfront get-distribution --id $CfDist --query "Distribution.DomainName" --output text 2>$null
    Write-Host "CloudFront: https://$CfDomain"
}
Write-Host "`nNote: CloudFront requires account verification for new distributions." -ForegroundColor Yellow
