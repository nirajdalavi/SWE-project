// Cloudflare Worker for domain routing (if needed)
// Since we now use separate domains (aqeed-aws.cloud and aqeed-gcp.cloud),
// this worker is no longer needed for routing.
// Each domain points directly to its respective server.

export default {
  async fetch(request) {
    // For now, just pass through the request
    return fetch(request);
  }
}
