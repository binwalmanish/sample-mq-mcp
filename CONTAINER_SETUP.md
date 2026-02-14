# IBM MQ Container Setup for MCP Server

This document describes the IBM MQ container configuration that works with this MCP server.

## Current Container Configuration

Your MQ container is running with the following configuration:

```bash
docker run \
  --platform linux/amd64 \
  --env LICENSE=accept \
  --env MQ_QMGR_NAME=QM1 \
  --env MQ_ADMIN_PASSWORD=passw0rd \
  --env MQ_APP_PASSWORD=passw0rd \
  --publish 1414:1414 \
  --publish 9443:9443 \
  --volume ibm-mq-data:/mnt/mqm \
  --detach \
  icr.io/ibm-messaging/mq
```

## Container Details

- **Image**: `icr.io/ibm-messaging/mq` (latest)
- **Queue Manager Name**: `QM1`
- **Admin Credentials**: `admin` / `passw0rd`
- **App Credentials**: `app` / `passw0rd`

### Exposed Ports

- **1414**: MQ Listener port (for MQ client connections)
- **9443**: MQ Web Console and REST API

### Volume

- **ibm-mq-data**: Persistent volume for queue manager data at `/mnt/mqm`

## Accessing the MQ Container

### Web Console
Access the MQ Web Console at:
```
https://localhost:9443/ibmmq/console
```

Login with:
- Username: `admin`
- Password: `passw0rd`

### REST API
The MQ REST API is available at:
```
https://localhost:9443/ibmmq/rest/v3/admin/
```

Test with curl:
```bash
curl -k https://localhost:9443/ibmmq/rest/v3/admin/qmgr/ \
  -u admin:passw0rd \
  -H "ibm-mq-rest-csrf-token: token"
```

### Docker Commands

Check container status:
```bash
docker ps | grep mq
```

View container logs:
```bash
docker logs <container-id>
```

Stop the container:
```bash
docker stop <container-id>
```

Start the container again:
```bash
docker start <container-id>
```

Remove the container:
```bash
docker rm -f <container-id>
```

## MCP Server Configuration

The MCP server (`mqmcpserver.py`) is configured to connect to this container:

```python
URL_BASE = "https://localhost:9443/ibmmq/rest/v3/admin/"
USER_NAME = "admin"
PASSWORD = "passw0rd"
```

## Multiple Containers

You have multiple MQ containers running:

1. Container on ports **9443** and **1414** - Primary (used by MCP server)
2. Container on ports **9444** and **1415** - Secondary (QM2)

To use the secondary container, update `mqmcpserver.py`:
```python
URL_BASE = "https://localhost:9444/ibmmq/rest/v3/admin/"
```

## Creating a New Container

If you need to create a fresh MQ container:

```bash
# Create volume
docker volume create ibm-mq-data

# Run container
docker run \
  --platform linux/amd64 \
  --env LICENSE=accept \
  --env MQ_QMGR_NAME=QM1 \
  --env MQ_ADMIN_PASSWORD=passw0rd \
  --env MQ_APP_PASSWORD=passw0rd \
  --publish 1414:1414 \
  --publish 9443:9443 \
  --volume ibm-mq-data:/mnt/mqm \
  --detach \
  --name mq-server \
  icr.io/ibm-messaging/mq
```

## Troubleshooting

### Container won't start
Check if ports are already in use:
```bash
lsof -i :9443
lsof -i :1414
```

### Can't connect to REST API
1. Verify container is running: `docker ps`
2. Check container logs: `docker logs <container-id>`
3. Test with curl (see REST API section above)

### Permission denied errors
The container runs as user `mqm` (UID 888). Ensure volume permissions are correct.

## Security Notes

⚠️ **Warning**: The default password `passw0rd` is for development/testing only.

For production use:
- Change the admin password using environment variables
- Use TLS certificates instead of self-signed
- Restrict network access to the container
- Use proper authentication mechanisms

## References

- [IBM MQ Container Documentation](https://github.com/ibm-messaging/mq-container)
- [MQ REST API Reference](https://www.ibm.com/docs/en/ibm-mq/9.4?topic=reference-rest-api)
- [MQ Developer Container](https://developer.ibm.com/tutorials/mq-connect-app-queue-manager-containers/)
