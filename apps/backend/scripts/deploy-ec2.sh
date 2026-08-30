#!/bin/bash
# ============================================================
# DASH Backend — AWS EC2 Free Tier Deployment
# Deploys to t2.micro (free for 12 months)
#
# Prerequisites:
#   - AWS account with free tier
#   - AWS CLI configured (aws configure)
# ============================================================

set -e

echo "╔══════════════════════════════════════════╗"
echo "║   DASH — AWS EC2 Deployment             ║"
echo "╚══════════════════════════════════════════╝"
echo ""

# Check AWS CLI
if ! command -v aws &> /dev/null; then
    echo "ERROR: AWS CLI not installed"
    echo "Install: https://aws.amazon.com/cli/"
    exit 1
fi

echo "This script will:"
echo "  1. Create a t2.micro EC2 instance (free tier)"
echo "  2. Install Docker on it"
echo "  3. Deploy the DASH backend"
echo "  4. Configure security group for HTTPS"
echo ""
echo "Cost: \$0/mo for 12 months (free tier)"
echo ""

# Step 1: Create EC2 instance
echo "[1/4] Creating EC2 instance..."

# Use Amazon Linux 2023 (free tier eligible)
INSTANCE_ID=$(aws ec2 run-instances \
    --image-id ami-0c7217cdde317cfec \
    --instance-type t2.micro \
    --key-name dash-key \
    --security-group-ids sg-xxxxxxxx \
    --subnet-id subnet-xxxxxxxx \
    --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=dash-backend}]' \
    --user-data '#!/bin/bash
yum update -y
yum install -y docker
systemctl start docker
systemctl enable docker
usermod -aG docker ec2-user
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
' \
    --query 'Instances[0].InstanceId' \
    --output text 2>/dev/null)

echo "  Instance ID: $INSTANCE_ID"
echo "  Waiting for instance to start..."

aws ec2 wait instance-status-ok --instance-ids "$INSTANCE_ID"

# Get public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "  Public IP: $PUBLIC_IP"

# Step 2: Create security group
echo "[2/4] Configuring security group..."

SG_ID=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' \
    --output text)

# Allow HTTP, HTTPS, SSH
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 80 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 443 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 22 --cidr 0.0.0.0/0
aws ec2 authorize-security-group-ingress --group-id "$SG_ID" --protocol tcp --port 8000 --cidr 0.0.0.0/0

echo "  Security group configured"

# Step 3: Deploy via SSH
echo "[3/4] Deploying backend..."

# Wait a bit for user-data to finish
echo "  Waiting for Docker to install (2 minutes)..."
sleep 120

# SSH and deploy
ssh -o StrictHostKeyChecking=no ec2-user@"$PUBLIC_IP" << 'REMOTE'
# Clone the repo
cd /home/ec2-user
git clone https://github.com/shadow909559/dash.git
cd dash/apps/backend

# Create docker-compose
cat > docker-compose.yml << 'YAML'
version: "3.8"
services:
  backend:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DASH_ENV=production
      - HOST=0.0.0.0
      - DATABASE_URL=postgresql://dash:dash@db:5432/dash
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    restart: always

  db:
    image: postgres:16-alpine
    environment:
      - POSTGRES_USER=dash
      - POSTGRES_PASSWORD=dash
      - POSTGRES_DB=dash
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    restart: always

volumes:
  pgdata:
YAML

# Start services
docker-compose up -d --build

echo "Backend deployed at http://localhost:8000"
REMOTE

echo "  Backend deployed!"

# Step 4: Print connection details
echo "[4/4] Setup complete!"
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   EC2 Deployment Complete               ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Backend URL: http://$PUBLIC_IP:8000"
echo "Health check: curl http://$PUBLIC_IP:8000/health"
echo ""
echo "To connect your apps:"
echo "  Server IP: $PUBLIC_IP"
echo "  Port: 8000"
echo ""
echo "To set up HTTPS (recommended):"
echo "  1. Point a domain to $PUBLIC_IP"
echo "  2. Use Certbot for free SSL:"
echo "     ssh ec2-user@$PUBLIC_IP"
echo "     sudo apt install certbot nginx"
echo "     sudo certbot --nginx -d yourdomain.com"
echo ""
echo "To set secrets:"
echo "  ssh ec2-user@$PUBLIC_IP"
echo "  cd dash/apps/backend"
echo "  # Edit .env file with your keys"
echo "  docker-compose restart backend"
