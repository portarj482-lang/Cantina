---
name: ubuntu-rpc
description: >-
  Procedures and CLI commands for Ubuntu RPC service discovery (rpcbind), service query (rpcinfo),
  and SMB/Windows RPC execution (rpcclient). Use when working with RPC daemons, querying registered
  port 111 programs, or interacting with Samba/Windows RPC services.
---

# Ubuntu Command Line RPC Workflows

This skill provides step-by-step procedures and commands for configuring and utilizing Remote Procedure Call (RPC) services on Ubuntu.

---

## 1. Architecture Overview

- **Port 111 (TCP/UDP)**: Standard Portmapper/RPCbind port mapping RPC program numbers to network port numbers.
- **`rpcbind`**: Universal RPC service discovery daemon that maps RPC program numbers into DARPA protocol port addresses.
- **`rpcinfo`**: Queries the RPC portmapper on a local or remote host to report registered RPC programs, versions, and protocol bindings.
- **`rpcclient`**: Part of the Samba suite, providing an interactive client or one-liner tool to execute MS-RPC / SMB RPC calls against Windows or Samba servers.

---

## 2. Installation & Service Setup

### 2.1 Installing `rpcbind`
```bash
sudo apt update
sudo apt install -y rpcbind
```

### 2.2 Enabling and Starting the Service
```bash
sudo systemctl enable rpcbind
sudo systemctl start rpcbind
sudo systemctl status rpcbind --no-pager
```

---

## 3. Querying RPC Services (`rpcinfo`)

### 3.1 List All Registered Local RPC Services
```bash
rpcinfo -p
```
*Expected output schema:*
```text
   program vers proto   port  service
    100000    4   tcp    111  portmapper
    100000    3   tcp    111  portmapper
    100000    2   tcp    111  portmapper
    100000    4   udp    111  portmapper
    100000    3   udp    111  portmapper
    100000    2   udp    111  portmapper
```

### 3.2 Query a Remote Host
```bash
rpcinfo -p <target_host_or_ip>
```

### 3.3 Query a Specific RPC Program Number
To test if a specific program (e.g., program `100003` for NFS, `100005` for mountd, `100024` for status) is registered:
```bash
rpcinfo -t <target_host> <program_number> <version>
# Example: test NFS v3
rpcinfo -t 192.168.1.10 100003 3
```

---

## 4. Executing SMB/Windows RPC Calls (`rpcclient`)

`rpcclient` is provided by the Samba client suite.

### 4.1 Installing Samba Utilities
```bash
sudo apt install -y samba-common-bin smbclient
# Or full samba package
sudo apt install -y samba
```

### 4.2 Connection Syntax
```bash
rpcclient [-U username%password] [-I target_ip] <server>
```

### 4.3 Common Connection Options
- `-N`: Anonymous login (no password requested or sent).
- `-U <user>%<pass>`: Specify credentials inline.
- `-c "<command>"`: Execute a single command and immediately exit.
- `-d <debug_level>`: Increase verbosity (0-10) for troubleshooting network negotiation.

### 4.4 Example Commands Inside `rpcclient`
```bash
# Connect with credentials
rpcclient -U admin%password 192.168.1.10

# In the interactive prompt:
rpcclient $> net use
rpcclient $> net share
rpcclient $> enumdomusers
rpcclient $> queryuser <username>
rpcclient $> net user add <username> <password>
```

### 4.5 One-Shot Commands
```bash
# Enumerate shares anonymously
rpcclient -N -c "net share" 192.168.1.10

# Enumerate domain users with credentials
rpcclient -U admin%password -c "enumdomusers" 192.168.1.10
```

---

## 5. Firewall Configuration (UFW)

Ensure port 111 (and any specific registered service ports like 2049 for NFS) are permitted if querying across networks:

```bash
# Allow RPC portmapper
sudo ufw allow 111/tcp
sudo ufw allow 111/udp

# If SMB RPC is also exposed:
sudo ufw allow 445/tcp
sudo ufw allow 139/tcp
```

---

## 6. Cheatsheet Summary

| Task | Command |
|---|---|
| Install RPCbind | `sudo apt update && sudo apt install -y rpcbind` |
| Start RPCbind | `sudo systemctl enable --now rpcbind` |
| List local RPC programs | `rpcinfo -p` |
| List remote RPC programs | `rpcinfo -p <host>` |
| Query RPC program via TCP | `rpcinfo -t <host> <prog_num> <version>` |
| Query RPC program via UDP | `rpcinfo -u <host> <prog_num> <version>` |
| Install Samba RPC client | `sudo apt install -y samba-common-bin` |
| Execute RPC command (Anonymous) | `rpcclient -N -c "<cmd>" <host>` |
| Execute RPC command (Authenticated) | `rpcclient -U user%pass -c "<cmd>" <host>` |
| Allow RPC through UFW | `sudo ufw allow 111/tcp && sudo ufw allow 111/udp` |
