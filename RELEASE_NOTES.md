# 🚀 Release v1.0.0 — Initial Release of XP2AIOM

We are excited to announce the initial release of **XP2AIOM (Nuvio / Xperience ➔ AIOMetadata Bridge)**!

XP2AIOM makes migrating your custom layouts, widget configurations, and catalogs from Nuvio / Xperience into Stremio's AIOMetadata addon seamless and effortless.

---

### 🌟 Key Highlights

- **🔑 Direct Nuvio Account Login**: Log in with your Nuvio/Xperience account to automatically fetch your layout and active widgets.
- **🔗 Manifest & Preset Importer**: Full support for importing via direct Stremio `manifest.json` URLs, drag-and-drop file upload, or raw JSON paste.
- **🧬 AIOMetadata Base Config Merging**: Upload your current `aiometadata-config.json` to preserve your API keys (TMDB, Trakt, RPDB, Gemini, MDBList), Art Providers, and custom descriptions while updating your catalogs.
- **📊 Real-time Interactive Dashboard**: Filter and search through detected catalogs, toggle catalogs active/inactive, customize naming prefixes (`[Discover]`, `[Streaming Services]`), and adjust rating posters (RPDB).
- **🐳 Multi-Arch Docker & Unraid Ready**: Multi-arch container images (`linux/amd64`, `linux/arm64`) published to GitHub Container Registry (`ghcr.io/mckenna654/xp2aiom`) with a dedicated Unraid template (`unraid-template.xml`).

---

### 📦 Installation

#### Unraid Template
Add `https://raw.githubusercontent.com/mckenna654/xp2aiom/main/unraid-template.xml` to your Unraid template repositories.

#### Docker Compose
```yaml
version: "3.8"

services:
  xp2aiom:
    image: ghcr.io/mckenna654/xp2aiom:latest
    container_name: xp2aiom
    restart: unless-stopped
    ports:
      - "7088:7088"
```
