/**
 * HyperFlash Agent Dashboard Configuration
 *
 * Copy this file to config.local.js and customize the values for your deployment.
 * The config.local.js file is ignored by git.
 */

// Dashboard configuration
const CONFIG = {
  // Your agent dashboard URL (for meta tags and sharing)
  DASHBOARD_URL: 'https://agent.hyperflash.uk/',

  // Your metrics API endpoint
  AGENT_API: 'https://api.hyperflash.uk/metrics?token=YOUR_TOKEN_HERE',

  // Umami analytics (optional - set to null to disable)
  UMAMI_URL: 'https://umami.hyperflash.uk/script.js',
  UMAMI_WEBSITE_ID: 'e241baef-c722-4136-b643-59c025d0cfaa',

  // Cloudflare Web Analytics (optional - set to null to disable)
  CLOUDFLARE_BEACON_TOKEN: '73c22e1949594603a05fa23b29997570',

  // Domain name to display in SSL certificate badge
  DOMAIN_NAME: 'agent.hyperflash.uk',

  // Branding
  BRAND_NAME: 'Hyperflash',
  BRAND_URL: 'https://hyperflash.uk',

  // Page title and description
  PAGE_TITLE: 'Agent | VPS Dashboard',
  PAGE_DESCRIPTION: 'AI-powered VPS monitoring dashboard',
  PAGE_AUTHOR: 'Hyperflash',
};

// Export for use in HTML files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CONFIG;
}
