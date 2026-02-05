# Dual Cloud Setup: aqeed.ai/aws and aqeed.ai/gcp

This guide shows how to set up both AWS and GCP deployments with path-based routing on the same domain.

## 🌐 DNS Configuration Strategy

### Option 1: Single Domain with Load Balancer (Recommended)
- **Main domain**: `aqeed.ai` → Load balancer
- **AWS path**: `aqeed.ai/aws` → AWS EC2 instance
- **GCP path**: `aqeed.ai/gcp` → GCP Compute Engine instance
- **Root**: `aqeed.ai` → Your Framer site

### Option 2: Subdomain Approach
- **Main site**: `aqeed.ai` → Your Framer site
- **AWS**: `aws.aqeed.ai` → AWS EC2 instance  
- **GCP**: `gcp.aqeed.ai` → GCP Compute Engine instance

## 🚀 Current Setup (Path-Based Routing)

### AWS Configuration
- **File**: `docker-compose-aws.yaml`
- **Nginx**: `nginx-aws.conf`
- **SSL**: `setup-ssl-aws.sh`
- **Route**: `aqeed.ai/aws`

### GCP Configuration  
- **File**: `docker-compose-gcp.yaml`
- **Nginx**: `nginx-gcp.conf`
- **SSL**: `setup-ssl-gcp.sh`
- **Route**: `aqeed.ai/gcp`

## 📋 Deployment Process

### 1. DNS Setup
You'll need to decide which instance gets the main domain:

**For AWS to handle main domain:**
```
aqeed.ai → AWS EC2 IP
```

**For GCP to handle main domain:**
```
aqeed.ai → GCP Compute Engine IP
```

### 2. Deploy Both Instances
Both workflows will run in parallel:
- AWS workflow uses `docker-compose-aws.yaml`
- GCP workflow uses `docker-compose-gcp.yaml`

### 3. SSL Certificates
Both instances will generate SSL certificates for `aqeed.ai`

## 🎯 Access Points

### If AWS handles main domain:
- `https://aqeed.ai` → Redirects to Framer site
- `https://aqeed.ai/aws` → AWS deployment
- `https://aqeed.ai/gcp` → GCP deployment (via redirect)

### If GCP handles main domain:
- `https://aqeed.ai` → Redirects to Framer site  
- `https://aqeed.ai/gcp` → GCP deployment
- `https://aqeed.ai/aws` → AWS deployment (via redirect)

## 🔧 Configuration Files

### AWS Files:
- `docker-compose-aws.yaml` - AWS-specific compose file
- `nginx-aws.conf` - AWS Nginx configuration
- `setup-ssl-aws.sh` - AWS SSL setup script

### GCP Files:
- `docker-compose-gcp.yaml` - GCP-specific compose file
- `nginx-gcp.conf` - GCP Nginx configuration  
- `setup-ssl-gcp.sh` - GCP SSL setup script

### Workflows:
- `.github/workflows/build.yml` - AWS deployment
- `.github/workflows/deploy-gcp.yml` - GCP deployment

## 🚨 Important Considerations

### 1. DNS Conflict
Both instances will try to handle `aqeed.ai`. You need to choose one as primary.

### 2. SSL Certificate
Only the primary instance should generate SSL certificates to avoid conflicts.

### 3. Load Balancing
For true dual-cloud setup, consider using a load balancer service.

## 🎯 Recommended Approach

### Phase 1: Test Both Separately
1. Deploy AWS with `aws.aqeed.ai` subdomain
2. Deploy GCP with `gcp.aqeed.ai` subdomain
3. Test both deployments

### Phase 2: Choose Primary
1. Decide which cloud to use as primary
2. Point main domain to primary instance
3. Set up redirects for secondary

### Phase 3: Load Balancing (Optional)
1. Use CloudFlare or similar service
2. Set up health checks
3. Route traffic based on availability

## 🔄 Next Steps

1. **Choose your primary cloud** (AWS or GCP)
2. **Update DNS** to point main domain to primary
3. **Deploy both instances** using the workflows
4. **Test both routes** work correctly
5. **Set up monitoring** for both deployments

This gives you redundancy across both cloud providers while maintaining a clean URL structure!
