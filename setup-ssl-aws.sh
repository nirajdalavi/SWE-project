#!/bin/bash

# SSL Certificate Setup Script for AWS EC2 Instance
# Run this on your AWS EC2 instance after deployment

echo "Setting up SSL certificates for aqeed-aws.cloud on AWS..."

# Install Certbot
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# Create webroot directory
sudo mkdir -p /var/www/html
sudo chown ubuntu:ubuntu /var/www/html

# Generate SSL certificate for subdomain
echo "Generating SSL certificate..."
sudo certbot certonly --webroot \
  --webroot-path /var/www/html \
  --email madhur@allyin.ai \
  --agree-tos \
  --no-eff-email \
  -d aqeed-aws.cloud

# Set up automatic renewal
echo "Setting up automatic certificate renewal..."
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet") | crontab -

echo "SSL setup complete!"
echo "Certificates are now in: /etc/letsencrypt/live/aqeed-aws.cloud/"
echo "You can now restart your Docker containers:"
echo "cd /home/ubuntu/AqeedAI && docker compose -f docker-compose-aws.yaml down && docker compose -f docker-compose-aws.yaml up -d"
