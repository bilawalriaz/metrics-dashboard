# Metrics Dashboard

Real-time VPS monitoring dashboard with Python metrics agent and web frontend.

**Live Demo:** https://agent.hyperflash.uk

---

## Overview

This project provides a complete VPS monitoring solution with:
- **Python metrics agent** - High-performance system metrics collector
- **Web dashboard** - Real-time frontend with 2-second refresh
- **Token-based API** - Secure metrics endpoint
- **Zero dependencies** - Runs in a single Docker container
- **Configurable** - Easy to deploy to any domain with custom branding

---

## Quick Start for Your Own Deployment

### 1. Clone the Repository

```bash
git clone https://github.com/bilawalriaz/metrics-dashboard.git
cd metrics-dashboard
```

### 2. Configure Your Dashboard

Copy the example config file and customize it for your domain:

```bash
cp config.local.js.example config.local.js
```

Edit `config.local.js` with your settings:

```javascript
const CONFIG = {
  // Your dashboard URL
  DASHBOARD_URL: 'https://your-domain.com/',

  // Your metrics API endpoint
  AGENT_API: 'https://api.your-domain.com/metrics?token=YOUR_TOKEN_HERE',

  // Your domain name for SSL badge
  DOMAIN_NAME: 'your-domain.com',

  // Your branding
  BRAND_NAME: 'Your Brand',
  BRAND_URL: 'https://your-brand.com',

  // Optional analytics (set to null to disable)
  UMAMI_URL: null,
  UMAMI_WEBSITE_ID: null,
  CLOUDFLARE_BEACON_TOKEN: null,
};
```

### 3. Deploy the Frontend

Upload the HTML files (`index.html`, `alt.html`, `simple.html`) and `config.js` to your web server.

**Important:** Upload `config.local.js` as well, but ensure your web server doesn't expose it publicly if it contains sensitive tokens.

### 4. Deploy the Metrics Agent

See the [Architecture](#architecture) section below for details on setting up the metrics agent backend.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              INTERNET                                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLOUDFLARE TUNNEL                                │
│  ┌─────────────────────────┐    ┌─────────────────────────┐            │
│  │ agent.hyperflash.uk     │    │ api.hyperflash.uk       │            │
│  │ → localhost:80 (Caddy)  │    │ → localhost:80 (Caddy)  │            │
│  └─────────────────────────┘    └─────────────────────────┘            │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         CADDY (Docker)                                   │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │ agent.hyperflash.uk → Serves static frontend files             │   │
│  ├─────────────────────────────────────────────────────────────────┤   │
│  │ api.hyperflash.uk/metrics?token=SECRET                           │
│  │   - Token authentication                                        │   │
│  │   - Proxies → metrics-agent container (Docker)                 │   │
│  └─────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    METRICS AGENT (Docker container)                      │
│  - Python agent exposing JSON at /metrics                               │
│  - Reads from /proc for accurate system metrics                         │
│  - Docker socket access for container status                            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Project Structure

```
metrics-dashboard/
├── index.html            # Main dashboard
├── alt.html              # Alternative layout
├── simple.html           # Minimal version
├── config.js             # Default configuration (included in git)
├── config.local.js       # Your local overrides (not in git)
├── config.local.js.example # Example configuration file
├── .gitignore            # Ignores config.local.js
├── LICENSE               # MIT License
└── README.md             # This file
```

**Note:** The `agent/` and `frontend/` directories referenced in older documentation are now consolidated in the root directory for simpler deployment.

---

## Configuration System

The dashboard uses a two-tier configuration system:

1. **config.js** - Default/example values (included in git)
2. **config.local.js** - Your personal overrides (ignored by git)

Any value in `config.local.js` will override the default in `config.js`. This makes it easy to:

- Deploy your own instance without committing secrets
- Share your config across multiple deployments
- Update the dashboard without losing your settings

### Configuration Options

| Setting | Description | Example |
|---------|-------------|---------|
| `DASHBOARD_URL` | Your dashboard URL (for meta tags) | `https://your-domain.com/` |
| `AGENT_API` | Your metrics API endpoint with token | `https://api.your-domain.com/metrics?token=xxx` |
| `UMAMI_URL` | Umami analytics script URL (optional) | `https://umami.your-domain.com/script.js` |
| `UMAMI_WEBSITE_ID` | Umami website ID (optional) | `your-website-id` |
| `CLOUDFLARE_BEACON_TOKEN` | Cloudflare analytics token (optional) | `your-token` |
| `DOMAIN_NAME` | Domain to display in SSL badge | `your-domain.com` |
| `BRAND_NAME` | Brand name for footer | `Your Brand` |
| `BRAND_URL` | Brand URL for footer link | `https://your-brand.com` |
| `PAGE_TITLE` | Page title | `Agent | VPS Dashboard` |
| `PAGE_DESCRIPTION` | Page description | `AI-powered VPS monitoring dashboard` |
| `PAGE_AUTHOR` | Page author | `Your Name` |

---

## API Endpoints

### GET /metrics

Returns system metrics as JSON.

**Authentication:** URL parameter `token=YOUR_SECRET_TOKEN`

**Response:**
```json
{
  "hostname": "vps-name",
  "uptime": 1234567,
  "cpu": {
    "percent": 15.2,
    "cores": [12.5, 8.3, 18.1, ...]
  },
  "memory": {
    "total": 8589934592,
    "used": 4294967296,
    "percent": 50.0
  },
  "disk": [...],
  "docker": {...},
  "processes": [...],
  "logs": [...]
}
```

**Query Parameters:**
- `?compact=1` - Minified JSON response

---

## Features

### Agent
- Per-core CPU usage tracking
- Memory and disk statistics
- Docker container status
- Top 5 processes by CPU/memory
- System logs (last 10 entries)
- Delta-based network rate calculations
- LRU-cached static system info

### Frontend
- Real-time updates (2-second interval)
- Responsive design
- Activity ticker
- Contact form integration
- Multiple layout options (index.html, alt.html, simple.html)
- Configurable branding and domain
- Optional analytics (Umami, Cloudflare)

---

## Requirements

- Docker and Docker Compose (for the metrics agent)
- Caddy web server (or equivalent reverse proxy)
- Linux host with /proc filesystem

---

## Deployment to Static Hosting

You can deploy just the frontend to any static hosting service:

- Netlify
- Vercel
- GitHub Pages
- Cloudflare Pages
- Any web server (Apache, Nginx, Caddy, etc.)

Simply upload the HTML files and `config.js` to your web host, and create a `config.local.js` file with your settings.

**Note:** For the full metrics functionality, you'll need to deploy the metrics agent backend separately.

---

## Customization

### Styling

All styles are inline in the HTML files using CSS variables. You can easily customize:

- Colors
- Fonts
- Spacing
- Shadows
- Gradients

Edit the `:root` variables at the top of the `<style>` section in any HTML file.

### Layout Variants

Three layout variants are included:

- **index.html**: Full-featured dashboard
- **alt.html**: Alternative layout
- **simple.html**: Minimal version

---

## Analytics (Optional)

The dashboard supports optional analytics via:

1. **Umami**: Set `UMAMI_URL` and `UMAMI_WEBSITE_ID` in config
2. **Cloudflare Web Analytics**: Set `CLOUDFLARE_BEACON_TOKEN` in config

To disable analytics, set these to `null` in your config.

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

You are free to:
- Use this project for personal or commercial purposes
- Modify the code for your needs
- Distribute modified versions
- Sublicense the code

Under the condition that you include the original copyright notice.

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

---

## Credits

- Built with vanilla HTML, CSS, and JavaScript
- No dependencies required
- Icons using SVG

---

## Support

For issues and questions, please open an issue on GitHub.

---

## Live Demo

See it in action at: https://agent.hyperflash.uk/

---

## Related Projects

- **[vps-config](https://github.com/bilawalriaz/vps-config)** - Complete VPS setup and configuration
- **[agent-contact-worker](https://github.com/bilawalriaz/agent-contact-worker)** - Contact form Cloudflare Worker
