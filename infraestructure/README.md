# Infrastructure
This directory contains the infrastructure-as-code for provisioning and deploying the Ask Junior application on Proxmox VE.

## Prerequisites
Ensure you have the following installed on your local machine:
- `wget`
- `make`
- `scp`
- `ssh`
- `virt-customize` (via `libguestfs-tools`)
- `ansible`

## Directory Structure
```bash
infraestructure/
├── Makefile                    # Main automation script
├── README.md                   # This file
└── provision/
    ├── inventory               # Ansible inventory file
    ├── deploy.yml              # Ansible playbook for deployment
    └── group_vars/
        └── all.yml             # Global variables
```

## Configuration
Before running, update the following variables in the `Makefile`:
| Variable | Description | Default |
|----------|-------------|---------|
| `VM_ID` | Proxmox VM ID | `112` |
| `VM_NAME` | VM name | `raw` |
| `PROXMOX_HOST` | Proxmox server IP | `10.0.0.42` |
| `PROXMOX_USER` | Proxmox user | `root` |
| `CIUSER` | Cloud-init user | `ubuntu` |
| `CIPASSWORD` | Cloud-init password | `ubuntu` |
| `CIIPADDRESS` | VM IP address | `10.0.0.112` |
| `CIGATEWAY` | Gateway IP | `10.0.0.1` |

Update `provision/inventory` if you change the IP address.

## Usage

### Full Deployment

Run all steps (download, upload, import, provision):
```bash
cd infraestructure
make all
```

### Individual Steps
```bash
# Download Ubuntu cloud image
make download

# Upload image to Proxmox
make upload

# Upload SSH key to Proxmox
make upload-key

# Create and configure VM on Proxmox
make import

# Run Ansible provisioning
make provision
```

## What Gets Deployed
The Ansible playbook (`provision/deploy.yml`) performs the following:

1. **System Setup**
   - Installs `git`, `docker.io`, and `docker-compose`
   - Starts and enables Docker service
   - Adds user to docker group

2. **Application Deployment**
   - Clones the repository from GitHub
   - Runs `docker compose up -d --build` for each service:
     - `agent/`
     - `monitor/`
     - `integrations/`
     - `traefik/`
     - `vector_database/`

## Ansible Variables
Defined in `provision/group_vars/all.yml`:
| Variable | Description |
|----------|-------------|
| `git_url` | Repository URL to clone |
| `agent_user` | System user for running services |
| `docker_group_name` | Docker group name |

### Re-running Provisioning

To re-run only the Ansible provisioning:

```bash
make provision
```

## Network Architecture

The VM is configured with:
- Static IP: `10.0.0.112/24`
- Gateway: `10.0.0.1`
- DNS: `8.8.8.8`
- Bridge: `vmbr0`
