# ---------- DEPENDENCIES ----------
# Ensure you have the following installed:
# - wget
# - make
# - scp
# - ssh
# - virt-customize (via libguestfs-tools)

# ---------- CONFIG VARIABLES ----------
VM_ID               = 112
VM_NAME             = raw
PROXMOX_HOST        = 10.0.0.42
PROXMOX_USER        = root
PROXMOX_TARGET_NODE = prx01
IMAGE_URL           = https://cloud-images.ubuntu.com/noble/current/noble-server-cloudimg-amd64.img
IMAGE_FILE          = ubuntu-cloud.img
CIUSER              = ubuntu
CIPASSWORD          = ubuntu
CISSHKEYS           = $(shell cat ~/.ssh/id_rsa.pub)
CIIPADDRESS         = 10.0.0.112
CIGATEWAY           = 10.0.0.1

# ---------- RULES ----------
.PHONY: all download upload upload-key import provision

all: download upload upload-key import provision

download:
	wget -O $(IMAGE_FILE) $(IMAGE_URL)
	@echo "Downloaded image to $(IMAGE_FILE)"

upload:
	@echo "Uploading image to Proxmox..."
	scp $(IMAGE_FILE) $(PROXMOX_USER)@$(PROXMOX_HOST):/var/lib/vz/template/

upload-key:
	@echo "Remove SSH keys if exists..."
	ssh-keygen -R $(CIIPADDRESS)
	@echo "Uploading SSH public key to Proxmox..."
	scp ~/.ssh/id_rsa.pub $(PROXMOX_USER)@$(PROXMOX_HOST):/tmp/$(VM_NAME).pub

import:
	@echo "Importing and configuring VM on Proxmox..."
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "apt install -y libguestfs-tools"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "\
	  virt-customize \
	    --add /var/lib/vz/template/$(IMAGE_FILE) \
	    --run-command 'sed -i s/archive.ubuntu.com/br.archive.ubuntu.com/g /etc/apt/sources.list' \
	    --run-command 'rm -rf /var/lib/apt/lists/*' \
	    --run-command 'apt-get clean' \
	    --run-command 'apt-get update' \
	    --install qemu-guest-agent,openssh-server \
	    --run-command 'systemctl enable ssh'"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm create $(VM_ID) --name $(VM_NAME) --memory 4096 --cores 2 --net0 virtio,bridge=vmbr0"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --machine q35"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm importdisk $(VM_ID) /var/lib/vz/template/$(IMAGE_FILE) local-lvm"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --scsihw virtio-scsi-pci --scsi0 local-lvm:vm-$(VM_ID)-disk-0"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --ide2 local-lvm:cloudinit"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --ciuser $(CIUSER) --cipassword $(CIPASSWORD)"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --sshkeys /tmp/$(VM_NAME).pub"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "rm /tmp/$(VM_NAME).pub"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --ipconfig0 ip=$(CIIPADDRESS)/24,gw=$(CIGATEWAY)"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --nameserver 8.8.8.8"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --boot c --bootdisk scsi0"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm disk resize $(VM_ID) scsi0 +50G"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --agent enabled=1"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm set $(VM_ID) --tags 'ubuntu,cloudinit,api,app,bot,docker,azure-agent'"
	ssh $(PROXMOX_USER)@$(PROXMOX_HOST) "qm start $(VM_ID)"

provision:
	@echo "Waiting for SSH to become available..."
	@until ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 ubuntu@$(CIIPADDRESS) 'echo SSH is ready'; do sleep 5; done
	@echo "Running Ansible deploy playbook..."
	ansible-playbook -i provision/inventory provision/deploy.yml