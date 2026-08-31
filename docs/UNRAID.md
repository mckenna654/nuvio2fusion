# Install Nuvio2Fusion on Unraid

Release: **v2.0.5** · Image: **`ghcr.io/mckenna654/nuvio2fusion:2.0.5`**

The image is public; no GitHub account or registry login is needed to pull it. Linux `amd64` and `arm64` images are published. Nuvio2Fusion runs as an unprivileged user and needs no appdata folder, database, media mounts, privileged mode or Docker socket access.

**Keep it on a trusted network.** There is no app authentication. Do not forward port 7088 through your router. A remote user's browser sends uploaded JSON to your Unraid server; converted files can contain private addon tokens. Use authenticated HTTPS or a VPN if access beyond your trusted LAN is needed.

## Install using the Unraid template

This is a direct template install; a Community Applications listing is not required and is not currently claimed.

1. Download [`unraid-template.xml`](https://github.com/mckenna654/nuvio2fusion/releases/download/v2.0.5/unraid-template.xml) from the release.
2. Save it on your Unraid boot device as `/boot/config/plugins/dockerMan/templates-user/my-nuvio2fusion.xml`. If that file already exists, back it up before replacing it. Unraid stores user Docker templates in this directory. [Unraid application documentation](https://docs.unraid.net/unraid-os/manual/applications/)
3. Open **Docker → Add Container** and choose **Nuvio2Fusion** from the user templates.
4. Leave **Network Type** as **Bridge** and privileged mode off. Keep the container port at **7088**. If the host port is taken, choose another host port, such as **7089**.
5. Apply/create the container. Once the image has downloaded, open its **WebUI**, or visit `http://YOUR-UNRAID-IP:7088` using your chosen host port. Enable **Auto-Start** if desired.

The template pins version `2.0.5` for a repeatable install. Its WebUI, icon, support link and port mapping are included. Unraid's official guide covers [bridge networking, port mappings and container management](https://docs.unraid.net/unraid-os/using-unraid-to/run-docker-containers/managing-and-customizing-containers/).

## Install through Add Container without the XML

Open **Docker → Add Container** and configure:

| Field | Value |
| --- | --- |
| Name | `Nuvio2Fusion` |
| Repository | `ghcr.io/mckenna654/nuvio2fusion:2.0.5` |
| Network Type | `Bridge` |
| Privileged | `Off` |
| Port mapping | Host `7088` → Container `7088`, TCP |
| WebUI, if shown in Advanced View | `http://[IP]:[PORT:7088]/` |
| Paths / volumes | None |
| Additional environment variables | None |

The image already sets `HOST=0.0.0.0` and `PORT=7088` internally. Do not set the container's `HOST` to `127.0.0.1`, as that would prevent access through its published port. `PUID` and `PGID` are not supported or needed.

## Use Docker Compose instead

Download [`docker-compose.release.yml`](https://github.com/mckenna654/nuvio2fusion/releases/download/v2.0.5/docker-compose.release.yml). The default host binding is localhost. For a trusted LAN, set `NUVIO2FUSION_BIND_IP` to your server's LAN IP before starting, replacing the example address below:

```sh
export NUVIO2FUSION_BIND_IP=192.168.1.10
docker compose -f docker-compose.release.yml pull
docker compose -f docker-compose.release.yml up -d
```

Keep this setting in your shell or a local `.env` file whenever you recreate the service. `NUVIO2FUSION_PORT` can change the host port. Do not launch both this service and the Unraid template on the same port.

## Convert your collections

1. Back up your current Fusion widgets and retain the original Nuvio collections export.
2. Upload the Nuvio collections JSON into Nuvio2Fusion.
3. Connect only the addons you use. For AIOMetadata, select `aio-metadata` and paste your configured URL ending in `/manifest.json`.
4. Convert and review the report. Optional addons such as Bingecat can stay blank: their sources are omitted with a warning. A folder relying entirely on a skipped addon will be empty.
5. Download the Fusion widget JSON and import it in Fusion. Keep the same configured catalog addons available to Fusion. Do not import the separate compatibility report.

Do not share generated widget files, private addon URLs or unsanitized screenshots in public Discord channels. Share the [project](https://github.com/mckenna654/nuvio2fusion) or [release](https://github.com/mckenna654/nuvio2fusion/releases/tag/v2.0.5) instead. The included examples deliberately use nonfunctional placeholder URLs.

## Updates, verification and troubleshooting

- **Pinned version:** edit the Repository field to a newer published version and apply. To follow successful builds of `main`, use `ghcr.io/mckenna654/nuvio2fusion:latest` and Unraid's update controls instead. `latest` may include changes newer than a tagged release.
- **Verify:** open `http://YOUR-UNRAID-IP:7088/api/health`; this release reports `Nuvio2Fusion`, version `2.0.5`, status `ok`. The image also includes a Docker health check.
- **Page unreachable:** check the host/container port mapping, bridge network, container logs and LAN firewall. Change only the host port when resolving a port conflict.
- **Permission denied when pulling:** the package is public; use the exact `ghcr.io/mckenna654/nuvio2fusion:2.0.5` image name and check GitHub/registry connectivity.
- **Addon missing:** supply its configured manifest URL only if you want its sources. Downloads are blocked only when no usable sources or supported widgets remain.
- **Rollback:** choose a previously published image tag. No database or persistent application data needs migration. Save downloads and original Nuvio exports outside the container.

CI runs the conversion/API tests on Python 3.11 and 3.14, builds both Linux architectures, and starts the published image on an `amd64` runner to check health and example conversion. This does not replace verifying your own addon availability or your Unraid server's network configuration.
