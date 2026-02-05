# Redis Cloud Setup Guide

This guide explains how to deploy Redis with your AqeedAI application on AWS and GCP cloud platforms.

## Overview

Redis is used for:
- **Async Job Queue**: Managing background job processing for long-running tasks
- **Job Status Tracking**: Storing job states (PENDING, PROCESSING, SUCCESS, FAILED)
- **Session Management**: Temporary data storage for job results

## Cloud Deployment Changes

### 1. Docker Compose Updates

Both `docker-compose-aws.yaml` and `docker-compose-gcp.yaml` now include:

```yaml
redis:
  image: redis:7-alpine
  container_name: redis
  ports:
    - "6379:6379"
  volumes:
    - redis_data:/data
  restart: always
  networks:
    - default
  command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
```

**Key Features:**
- **Persistent Storage**: `--appendonly yes` ensures data survives container restarts
- **Memory Management**: 512MB limit with LRU eviction policy
- **High Availability**: Auto-restart on failure

### 2. Backend Dependencies

Redis is already included in `backend/requirements.txt`:
```
redis==5.0.1
```

### 3. Environment Configuration

#### For AWS Deployment:
```bash
# Copy environment template
cp env.aws.example .env

# Edit .env file with your actual values
nano .env
```

#### For GCP Deployment:
```bash
# Copy environment template
cp env.gcp.example .env

# Edit .env file with your actual values
nano .env
```

**Required Environment Variables:**
```bash
REDIS_URL=redis://redis:6379/0
QDRANT_URL=http://qdrant:6333
ENVIRONMENT=production
DEBUG=false
```

## Deployment Steps

### AWS Deployment

1. **Prepare Environment:**
   ```bash
   cp env.aws.example .env
   # Edit .env with your AWS-specific values
   ```

2. **Deploy Services:**
   ```bash
   docker-compose -f docker-compose-aws.yaml up -d
   ```

3. **Verify Redis Connection:**
   ```bash
   # Check Redis container
   docker logs redis
   
   # Test connection from backend
   docker exec fastapi-backend python -c "
   import redis
   r = redis.Redis.from_url('redis://redis:6379/0')
   print('Redis connection:', r.ping())
   "
   ```

### GCP Deployment

1. **Prepare Environment:**
   ```bash
   cp env.gcp.example .env
   # Edit .env with your GCP-specific values
   ```

2. **Deploy Services:**
   ```bash
   docker-compose -f docker-compose-gcp.yaml up -d
   ```

3. **Verify Redis Connection:**
   ```bash
   # Check Redis container
   docker logs redis
   
   # Test connection from backend
   docker exec fastapi-backend python -c "
   import redis
   r = redis.Redis.from_url('redis://redis:6379/0')
   print('Redis connection:', r.ping())
   "
   ```

## Monitoring and Maintenance

### Health Checks

**Check Redis Status:**
```bash
# Via API endpoint
curl https://your-domain.com/worker/status

# Expected response:
{
  "status": "running",
  "redis_connected": true,
  "jobs_in_queue": 0,
  "worker_thread_alive": true
}
```

**Direct Redis Commands:**
```bash
# Connect to Redis container
docker exec -it redis redis-cli

# Check memory usage
INFO memory

# List all keys
KEYS *

# Check job queue
KEYS job:*
```

### Data Persistence

Redis data is stored in the `redis_data` Docker volume:
- **Location**: `/data` inside the Redis container
- **Persistence**: Data survives container restarts
- **Backup**: Volume is backed up with your Docker volumes

### Performance Tuning

**Memory Configuration:**
- **Current Limit**: 512MB
- **Eviction Policy**: LRU (Least Recently Used)
- **Persistence**: AOF (Append Only File)

**To increase memory limit:**
```yaml
# In docker-compose file
command: redis-server --appendonly yes --maxmemory 1gb --maxmemory-policy allkeys-lru
```

## Troubleshooting

### Common Issues

1. **Redis Connection Failed:**
   ```bash
   # Check if Redis container is running
   docker ps | grep redis
   
   # Check Redis logs
   docker logs redis
   ```

2. **Job Processing Stopped:**
   ```bash
   # Check worker thread status
   curl https://your-domain.com/worker/status
   
   # Restart backend if needed
   docker-compose restart backend
   ```

3. **Memory Issues:**
   ```bash
   # Check Redis memory usage
   docker exec redis redis-cli INFO memory
   
   # Clear old jobs if needed
   docker exec redis redis-cli FLUSHDB
   ```

### Logs

**Redis Logs:**
```bash
docker logs redis -f
```

**Backend Worker Logs:**
```bash
docker logs fastapi-backend -f | grep "Worker"
```

## Production Considerations

### Security

1. **Network Isolation**: Redis is only accessible within Docker network
2. **No External Access**: Port 6379 is not exposed to the internet
3. **Authentication**: Consider adding Redis AUTH for production

### Scaling

For high-traffic scenarios, consider:
1. **Redis Cluster**: Multiple Redis instances
2. **External Redis**: AWS ElastiCache or GCP Memorystore
3. **Load Balancing**: Multiple backend instances

### Backup Strategy

```bash
# Backup Redis data
docker exec redis redis-cli BGSAVE

# Copy backup file
docker cp redis:/data/dump.rdb ./redis-backup-$(date +%Y%m%d).rdb
```

## Next Steps

1. Deploy to your cloud platform using the appropriate docker-compose file
2. Monitor the `/worker/status` endpoint to ensure Redis is working
3. Test async job functionality (QA, scoring, vendor operations)
4. Set up monitoring and alerting for Redis health
