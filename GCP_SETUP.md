# GCP Compute Engine Deployment Setup

This document explains how to set up the GCP Compute Engine deployment workflow that runs in parallel with your existing AWS EC2 workflow.

## Required GitHub Secrets

You need to add the following secrets to your GitHub repository:

### 1. GCP SSH Configuration (similar to EC2)
- `GCP_KEY`: Private SSH key for your GCP instance (same format as EC2_KEY)
- `GCP_USER`: SSH username for your GCP instance (usually `ubuntu` or your custom user)
- `GCP_HOST`: External IP address or hostname of your GCP Compute Engine instance

### 2. Shared Secrets (already used by EC2 workflow)
- `GIT_AUTH_TOKEN`: GitHub personal access token for cloning private repos
- `ENV_FILE`: Contents of your `.env` file

## GCP Setup Steps

### 1. Create a GCP Compute Engine Instance

```bash
# Create a new VM instance
gcloud compute instances create aqeedai-gcp \
  --zone=us-central1-a \
  --machine-type=e2-medium \
  --image-family=ubuntu-2004-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=20GB \
  --tags=http-server,https-server
```

### 2. Set up SSH Key Authentication

```bash
# Generate SSH key pair (if you don't have one)
ssh-keygen -t rsa -b 4096 -C "your-email@example.com" -f ~/.ssh/gcp_key

# Add the public key to your GCP instance
gcloud compute instances add-metadata aqeedai-gcp \
  --zone=us-central1-a \
  --metadata-from-file ssh-keys=~/.ssh/gcp_key.pub
```

### 3. Get Instance External IP

```bash
# Get the external IP of your instance
gcloud compute instances describe aqeedai-gcp \
  --zone=us-central1-a \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'
```

### 4. Configure Firewall Rules (if needed)

```bash
# Allow HTTP traffic
gcloud compute firewall-rules create allow-http \
  --allow tcp:80 \
  --source-ranges 0.0.0.0/0 \
  --target-tags http-server

# Allow HTTPS traffic
gcloud compute firewall-rules create allow-https \
  --allow tcp:443 \
  --source-ranges 0.0.0.0/0 \
  --target-tags https-server
```

## Workflow Features

The GCP workflow (`deploy-gcp.yml`) includes:

1. **Parallel Execution**: Runs simultaneously with your EC2 workflow
2. **Same Deployment Logic**: Identical Docker setup and application deployment
3. **GCP Authentication**: Uses Google Cloud SDK for secure authentication
4. **Error Handling**: Includes proper error handling and cleanup steps

## Workflow Structure

```
.github/workflows/
├── build.yml          # AWS EC2 deployment
└── deploy-gcp.yml     # GCP Compute Engine deployment (NEW)
```

Both workflows trigger on pushes to the `main` branch and can run in parallel, giving you redundancy and the ability to deploy to multiple cloud providers simultaneously.

## Monitoring Deployments

You can monitor both deployments in the GitHub Actions tab:
- AWS EC2 deployment: "Deploy to EC2"
- GCP deployment: "Deploy to GCP Compute Engine"

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Ensure the service account has proper permissions
2. **Zone/Instance Not Found**: Verify the zone and instance name in secrets
3. **Docker Installation Issues**: The workflow includes automatic Docker installation

### Debugging

To debug deployment issues, check the GitHub Actions logs for both workflows. The GCP workflow uses `gcloud compute ssh` which provides detailed error messages.
