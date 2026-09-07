#!/bin/bash
# Deploy DASH WoL Lambda Trigger to AWS
# Usage: bash deploy.sh

set -e

FUNCTION_NAME="dash-wol-trigger"
REGION="ap-south-1"
ROLE_NAME="dash-lambda-wol-role"

echo "=== Deploying DASH WoL Lambda Trigger ==="

# 1. Create IAM role for Lambda
echo "Creating IAM role..."
aws iam create-role \
    --role-name "$ROLE_NAME" \
    --assume-role-policy-document '{
        "Version": "2012-10-17",
        "Statement": [{
            "Effect": "Allow",
            "Principal": {"Service": "lambda.amazonaws.com"},
            "Action": "sts:AssumeRole"
        }]
    }' 2>/dev/null || echo "Role already exists"

# Attach policies
aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>/dev/null

aws iam attach-role-policy \
    --role-name "$ROLE_NAME" \
    --policy-arn "arn:aws:iam::aws:policy/AmazonSSMReadOnlyAccess" 2>/dev/null

# 2. Get role ARN
ROLE_ARN=$(aws iam get-role --role-name "$ROLE_NAME" --query 'Role.Arn' --output text)
echo "Role ARN: $ROLE_ARN"

# 3. Package the function
echo "Packaging..."
cd "$(dirname "$0")"
zip -r /tmp/wol-trigger.zip lambda_function.py

# 4. Create or update Lambda function
echo "Deploying Lambda function..."
aws lambda create-function \
    --function-name "$FUNCTION_NAME" \
    --runtime python3.12 \
    --role "$ROLE_ARN" \
    --handler lambda_function.handler \
    --zip-file fileb:///tmp/wol-trigger.zip \
    --region "$REGION" \
    --timeout 10 \
    --memory-size 128 \
    --environment "Variables={AWS_REGION=$REGION}" \
    2>/dev/null || \
aws lambda update-function-code \
    --function-name "$FUNCTION_NAME" \
    --zip-file fileb:///tmp/wol-trigger.zip \
    --region "$REGION"

# 5. Store WoL config in SSM
echo "Storing WoL config in SSM..."
aws ssm put-parameter --name "/dash/wol/mac_address" --value "AA:BB:CC:DD:EE:FF" --type "String" --overwrite 2>/dev/null
aws ssm put-parameter --name "/dash/wol/broadcast_ip" --value "192.168.1.255" --type "String" --overwrite 2>/dev/null
aws ssm put-parameter --name "/dash/wol/port" --value "9" --type "String" --overwrite 2>/dev/null
aws ssm put-parameter --name "/dash/wol/start_ec2" --value "false" --type "String" --overwrite 2>/dev/null
aws ssm put-parameter --name "/dash/wol/ec2_instance_id" --value "" --type "String" --overwrite 2>/dev/null

# 6. Create API Gateway
echo "Creating API Gateway..."
API_ID=$(aws apigatewayv2 create-api \
    --name "dash-wol-api" \
    --protocol-type "HTTP" \
    --query 'ApiId' \
    --output text 2>/dev/null || \
    aws apigatewayv2 get-apis --query "Items[?Name=='dash-wol-api'].ApiId" --output text)

echo "API ID: $API_ID"

# 7. Get Lambda function ARN
FUNCTION_ARN=$(aws lambda get-function \
    --function-name "$FUNCTION_NAME" \
    --region "$REGION" \
    --query 'Configuration.FunctionArn' \
    --output text)

# 8. Create API route and integration
echo "Setting up routes..."
INTEGRATION_ID=$(aws apigatewayv2 create-integration \
    --api-id "$API_ID" \
    --integration-type "AWS_PROXY" \
    --integration-uri "$FUNCTION_ARN" \
    --payload-format-version "2.0" \
    --query 'IntegrationId' \
    --output text 2>/dev/null)

aws apigatewayv2 create-route \
    --api-id "$API_ID" \
    --route-key "GET /wol" \
    --target "integrations/$INTEGRATION_ID" 2>/dev/null

aws apigatewayv2 create-route \
    --api-id "$API_ID" \
    --route-key "POST /wol" \
    --target "integrations/$INTEGRATION_ID" 2>/dev/null

# 9. Grant API Gateway permission to invoke Lambda
aws lambda add-permission \
    --function-name "$FUNCTION_NAME" \
    --statement-id "api-gateway-invoke" \
    --action "lambda:InvokeFunction" \
    --principal "apigateway.amazonaws.com" \
    --source-arn "arn:aws:execute-api:$REGION:752651103716:$API_ID/*" \
    --region "$REGION" 2>/dev/null

# 10. Create stage
aws apigatewayv2 create-stage \
    --api-id "$API_ID" \
    --stage-name "prod" \
    --auto-deploy \
    2>/dev/null

# Print result
echo ""
echo "=== Deployment Complete ==="
echo "Function: $FUNCTION_NAME"
echo "API URL: https://$API_ID.execute-api.$REGION.amazonaws.com/prod/wol"
echo ""
echo "Test with:"
echo "  curl https://$API_ID.execute-api.$REGION.amazonaws.com/prod/wol"
echo ""
echo "Update SSM params with your actual MAC/broadcast IP:"
echo "  aws ssm put-parameter --name '/dash/wol/mac_address' --value 'YOUR_MAC' --type String --overwrite"
echo "  aws ssm put-parameter --name '/dash/wol/broadcast_ip' --value 'YOUR_BROADCAST' --type String --overwrite"
