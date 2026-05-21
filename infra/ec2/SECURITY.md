# EC2 Security Notes

Current production hardening checklist:

- Restrict dashboard port `8080` to the operator public IP.
- Remove unused public ports such as `8050`.
- Keep dashboard Basic Auth enabled through `.env`.
- Keep `.env`, API keys, `.pem` files, runtime reports, and agent run logs out of Git.
- Prefer SSH tunnel or a domain with HTTPS before sharing the dashboard with anyone else.

## Current Dashboard Access Model

The dashboard is served by:

```text
commerce-dashboard.service
```

The agent run timer is:

```text
commerce-agents.timer
```

The retention cleanup timer is:

```text
commerce-cleanup.timer
```

Useful checks:

```bash
systemctl status commerce-dashboard.service
systemctl status commerce-agents.timer
sudo ufw status numbered
```

Commerce team also has a safe audit helper. It checks environment presence, file
permissions, tracked secret-like files, service status, disk pressure, and UFW
rules without printing secret values:

```bash
cd /opt/ai-adam-agent-company/teams/commerce-agent-team
.venv/bin/python scripts/ops_audit.py
```

Current UFW status:

```text
8080/tcp ALLOW IN 59.13.218.189
8080/tcp DENY IN Anywhere
8050/tcp removed
```

## Updating the Allowed Dashboard IP

Find the new public IP:

```bash
curl https://api.ipify.org
```

Then update UFW. Replace `NEW_PUBLIC_IP` with the actual value:

```bash
sudo ufw delete allow from 59.13.218.189/32 to any port 8080 proto tcp
sudo ufw allow from NEW_PUBLIC_IP/32 to any port 8080 proto tcp comment 'Commerce dashboard ADAM IP'
sudo ufw status numbered
```

Also update the AWS security group inbound rule for TCP `8080` to `NEW_PUBLIC_IP/32`.
