# isvd-ldap Helm Chart

Deploys **IBM Security Verify Directory (ISVD) 10.0.4** on Kubernetes with optional master-master
peer replication. A fully-automated orchestrator handles replication topology, PVC seeding, and
LDIF import in the correct order for ISVD.

---

## Table of Contents

1. [Repository Layout](#repository-layout)
2. [Template Files Explained](#template-files-explained)
3. [Values Reference](#values-reference)
4. [Deployment Topologies](#deployment-topologies)
5. [Step 1 — Install the Chart](#step-1--install-the-chart)
6. [Step 2 — Upload LDIF Files](#step-2--upload-ldif-files)
7. [Step 3 — Helm Upgrade (trigger orchestrator)](#step-3--helm-upgrade-trigger-orchestrator)
8. [Step 4 — Verify Users Exist](#step-4--verify-users-exist)
9. [Helm Test](#helm-test)
10. [Re-seeding a Stale Replica](#re-seeding-a-stale-replica)
11. [Uninstall](#uninstall)

---

## Repository Layout

```
isvd-ldap/
├── Chart.yaml                          # Chart metadata (name, version, appVersion)
├── values.yaml                         # Shared defaults for all environments
├── values-test.yaml                    # Test overlay: 2 instances (principal + 1 replica)
├── values-prod.yaml                    # Prod overlay: 4 instances (principal + 3 replicas)
├── ldif/
│   ├── users.ldif                      # Sample user directory data (LDIF format)
│   └── users.md5                       # MD5 checksum of users.ldif (integrity guard)
└── templates/
    ├── configmap-principal.yaml        # ISVD config for ldap-principal
    ├── configmap-replica.yaml          # ISVD config for each replica (one per entry in .Values.replicas)
    ├── deployment-principal.yaml       # Deployment + Service for ldap-principal
    ├── deployment-replica.yaml         # Deployment + Service per replica
    ├── deployment-ldif-loader.yaml     # Long-running pod that holds the LDIF staging PVC
    ├── job-seed.yaml                   # Replication orchestrator post-install/upgrade hook
    ├── podDisruptionBudget.yaml        # PDB to protect availability during node drains
    ├── pvc-ldif.yaml                   # PVC for LDIF staging (survives helm uninstall)
    ├── pvc-principal.yaml              # 10 Gi RWO PVC for principal data
    ├── pvc-replica.yaml                # 10 Gi RWO PVC per replica + seed-tmp PVC
    ├── secrets.yaml                    # Kubernetes Secret with adminPassword / replicationPassword
    ├── serviceaccount.yaml             # ServiceAccount, Role, RoleBinding for orchestrator
    └── tests/
        └── test-dn-count.yaml          # Helm test: DN count parity across all nodes
```

---

## Template Files Explained

### `configmap-principal.yaml`
Holds the ISVD `config.yaml` for `ldap-principal`:
- **server-id**: `isvd-principal`
- **port**: 10389 inside the container (Service maps this to 389; NodePort 30389 for external access)
- **suffix**: `o=sample` with `ibm-replicationContext` object class enabled
- Admin and replication passwords are injected from `values.yaml` at render time.

### `configmap-replica.yaml`
Generates one ConfigMap per entry in `.Values.replicas`. Each replica gets its own:
- Unique `server-id` (e.g. `isvd-replica-1`)
- Unique container port (e.g. 9389)
- Shared credentials from `values.yaml`

If `.Values.replicas` is empty (standalone mode) this file renders nothing.

### `deployment-principal.yaml`
Deploys `ldap-principal` as a single-pod Deployment:
- **Strategy**: `Recreate` — required because the data PVC is ReadWriteOnce (RWO); only one pod
  may mount it at a time.
- **Probes**: startup (up to 5 min for first DB init), liveness, and readiness all call
  `/sbin/health_check.sh` inside the container.
- **Resources**: 500m CPU / 512 Mi memory requested; 2 CPU / 2 Gi limit.
- Also creates the `ldap-principal` **Service** (NodePort 30389 → container 10389).

### `deployment-replica.yaml`
Generates one Deployment + one Service per entry in `.Values.replicas`:
- **spec.replicas is intentionally omitted** — the orchestrator job owns scaling via
  `kubectl scale` to avoid Helm field-manager conflicts.
- **Pod anti-affinity** (preferred) spreads replicas across nodes.
- **staleness-check init container** — runs on every pod restart. Reads the `.seeded_at` timestamp
  written by the orchestrator. If the replica has been offline longer than
  `ldif.replicationPurgeWindowHours` (default 20 h), it blocks startup and prints clear remediation
  instructions. This prevents the replica from serving stale data when ISVD's changelog has
  already been purged on the principal.

### `deployment-ldif-loader.yaml`
A minimal always-running pod (`sleep infinity`) that mounts `ldap-ldif-pvc`. Its sole purpose is
to provide a stable `kubectl cp` target for large LDIF files (tested with 300 MB+) — far above the
1 MB ConfigMap limit. Files written to it survive pod restarts because they live on the PVC.

Only rendered when `.Values.replicas` is non-empty.

### `job-seed.yaml`
The heart of the automated setup. Runs as a Helm **post-install / post-upgrade hook** and
orchestrates the full ISVD replication bootstrap:

| Step | Action |
|------|--------|
| 0    | Scale all replica Deployments to 0 immediately |
| 1    | Wait for `ldap-principal` to be Ready |
| 1b   | Check for `.migrated_at` marker on the LDIF PVC (idempotency) |
| 1c   | LDIF pre-flight — verify `users.ldif` present and MD5 matches |
| 5a   | `isvd_manage_replica -ap` on principal → register each replica |
| 5b   | `isvd_manage_replica -ar` on prior replicas → full-mesh agreements |
| 6    | Scale principal to 0 for safe binary PVC copy |
| 7    | Run inline seed Job — binary copy `ldap-principal-pvc` → `<replica>-pvc` |
| 8    | Scale principal back to 1; wait for Ready |
| 9    | Start replica; wait for Ready |
| 9b   | Write `.seeded_at` epoch timestamp to replica PVC |
| 10   | `isvd_manage_replica -ap` on replica → register principal (master-master reverse leg) |
| Post | Import `users.ldif` into principal via `ldapadd`; write `.migrated_at`; scale loader to 0 |

Steps 5–10 repeat for each replica in order.

Also contains the **seed ConfigMap** (`ldap-seed-config`) used by the inline seed Jobs.

### `podDisruptionBudget.yaml`
Protects LDAP availability during voluntary cluster disruptions (node drains, upgrades). Only
rendered when `.Values.replicas` is non-empty **and** `pdb.enabled` is `true`. Supports both
`minAvailable` and `maxUnavailable` strategies.

### `pvc-ldif.yaml`
PVC for LDIF staging (`ldap-ldif-pvc`). Annotated with `helm.sh/resource-policy: keep` so
`helm uninstall` does **not** delete it — your LDIF data survives across reinstalls.

### `pvc-principal.yaml`
10 Gi RWO PVC for `ldap-principal`'s data directory (`/var/isvd/data`).

### `pvc-replica.yaml`
Generates one 10 Gi RWO PVC per replica plus a shared 1 Gi `ldap-seed-tmp-pvc` for seed job logs.

### `secrets.yaml`
Kubernetes `Opaque` Secret holding `adminPassword` and `replicationPassword`. Used by:
- The orchestrator job (`ADMIN_PASSWORD` env var)
- The Helm test pod

### `serviceaccount.yaml`
Creates the `isvd` ServiceAccount plus a `Role` + `RoleBinding` granting the orchestrator
permissions to watch pods, exec into them, scale Deployments, and create/delete batch Jobs.

### `tests/test-dn-count.yaml`
Helm test pod that counts every DN under `o=sample` on the principal and all replicas using
`ldapsearch`. Passes only when:
1. The principal has a non-zero DN count (data was loaded).
2. Every replica's count equals the principal's count (replication is healthy).

---

## Values Reference

| Key | Default | Description |
|-----|---------|-------------|
| `adminPassword` | `Passw0rd1` | LDAP admin password (`cn=root`) — always override in prod |
| `replicationPassword` | `Passw0rd1` | ISVD replication admin password — always override in prod |
| `image.server` | `icr.io/isvd/verify-directory-server:latest` | ISVD server image |
| `image.seed` | `icr.io/isvd/verify-directory-seed:latest` | ISVD seed (PVC copy) image |
| `image.tools` | `bitnami/kubectl:latest` | Orchestrator image (needs kubectl + bash) |
| `image.pullPolicy` | `IfNotPresent` | Image pull policy |
| `replicas` | `[]` | List of replica instances; empty = standalone mode |
| `ldif.storage` | `1Gi` | Size of the LDIF staging PVC |
| `ldif.replicationPurgeWindowHours` | `20` | Hours before a stopped replica is considered stale |
| `pdb.enabled` | `true` | Enable PodDisruptionBudget |
| `pdb.name` | `isvd-ldap-pdb` | PDB resource name |
| `pdb.minAvailable` | `1` | Minimum pods that must stay running during disruptions |
| `pdb.maxUnavailable` | _(unset)_ | Alternative PDB strategy (mutually exclusive with minAvailable) |

Each entry in `.Values.replicas` requires:

| Field | Example | Description |
|-------|---------|-------------|
| `name` | `ldap-replica-1` | Kubernetes resource name and in-cluster DNS name |
| `serverId` | `isvd-replica-1` | ISVD server identity string |
| `port` | `9389` | Container port |
| `nodePort` | `31389` | External NodePort |

---

## Deployment Topologies

| Mode | Values file | Instances | NodePorts |
|------|-------------|-----------|-----------|
| Standalone (principal only) | `values.yaml` | 1 | 30389 |
| Test (2 instances) | `values-test.yaml` | 2 | 30389, 31389 |
| Production (4 instances) | `values-prod.yaml` | 4 | 30389, 31389, 32389, 33389 |

---

## Step 1 — Install the Chart

Create the namespace and install. On first install the orchestrator will start, wait for the
principal to be ready, then exit gracefully because no LDIF has been uploaded yet.

```bash
# Create namespace
kubectl create namespace isvd-ldap

# Standalone (no replication)
cd /Users/directory/projects/ibm-isvd/helm
helm install isvd-ldap ./isvd-ldap \
  --namespace isvd-ldap

# Test topology (principal + 1 replica)
cd /Users/directory/projects/ibm-isvd/helm
helm install isvd-ldap ./isvd-ldap \
  -f ./isvd-ldap/values-test.yaml \
  --namespace isvd-ldap

# Production topology (principal + 3 replicas)
cd /Users/suchi/projects/ibm-isvd/helm
helm install isvd-ldap ./isvd-ldap \
  -f ./isvd-ldap/values-prod.yaml \
  --namespace isvd-ldap
```

After install, wait for `ldap-principal` to be running:

```bash
kubectl get pods -n isvd-ldap -w
```

Expected output (test topology):

```
NAME                               READY   STATUS    RESTARTS
ldap-principal-<hash>              1/1     Running   0
ldap-ldif-loader-<hash>            1/1     Running   0
```

> `ldap-replica-1` will be at 0 replicas — this is intentional. The orchestrator scales it to 0
> immediately on startup (Step 0) and will scale it back to 1 after seeding.

---

## Step 2 — Upload LDIF Files

At this point `ldap-replica-1` is correctly at 0 (orchestrator ran Step 0). The `ldap-ldif-loader`
pod is up, waiting for LDIF files on its mounted PVC.

**Copy your LDIF and its MD5 checksum into the loader pod:**

```bash
# Identify the loader pod
THIS_POD=$(kubectl get pod -l role=ldif-loader \
  -n isvd-ldap \
  -o jsonpath='{.items[0].metadata.name}')
echo "Loader pod: $THIS_POD"

# Copy LDIF and checksum file
kubectl cp ldif/users.ldif isvd-ldap/$THIS_POD:/var/ldif/users.ldif
kubectl cp ldif/users.md5  isvd-ldap/$THIS_POD:/var/ldif/users.md5
```

**Generate a fresh MD5 if you don't have one:**

```bash
# Linux
md5sum ldif/users.ldif > ldif/users.md5

# macOS
md5 ldif/users.ldif > ldif/users.md5
```

**Verify the files landed correctly:**

```bash
kubectl exec -n isvd-ldap $THIS_POD -- ls -lh /var/ldif/
```

Expected:

```
-rw-r--r-- 1 root root  432 Mar  5 10:00 users.ldif
-rw-r--r-- 1 root root   55 Mar  5 10:00 users.md5
```

### LDIF Format Requirements

The LDIF **must** include the base entry `o=sample` first, then `ou=users,o=sample`, then user
entries. Without the base entry all child entries fail with `No such object`.

---

## Step 3 — Helm Upgrade (trigger orchestrator)

With the LDIF files in place, run `helm upgrade`. This triggers a new `post-upgrade` orchestrator
job that will:

1. Validate the LDIF MD5 checksum.
2. Register replication agreements (`isvd_manage_replica -ap`).
3. Seed each replica PVC from the principal (binary copy).
4. Import `users.ldif` into the principal via `ldapadd` (changes replicate automatically).
5. Write `.migrated_at` idempotency marker and scale the loader pod to 0.

```bash
cd /Users/suchi/projects/ibm-isvd/helm && helm upgrade isvd-ldap ./isvd-ldap \
  -f ./isvd-ldap/values-test.yaml \
  --namespace isvd-ldap 2>&1
```

**Monitor the orchestrator job:**

```bash
# Watch the job status
kubectl get jobs -n isvd-ldap -w

# Stream orchestrator logs in real time
kubectl logs -n isvd-ldap \
  -l role=seed-orchestrator \
  --follow
```

The orchestrator prints progress for every step. A successful run ends with:

```
=== Replication Orchestrator complete ===
  ldap-principal  running  NodePort 30389
  ldap-replica-1  running  NodePort 31389

Run 'helm test isvd-ldap' to verify replication is working.
```

**Check all pods are running after the upgrade:**

```bash
kubectl get pods -n isvd-ldap
```

```
NAME                               READY   STATUS      RESTARTS
ldap-principal-<hash>              1/1     Running     0
ldap-replica-1-<hash>              1/1     Running     0
ldap-seed-orchestrator-<hash>      0/1     Completed   0
```

---

## Step 4 — Verify Users Exist

Retrieve the admin password from the Kubernetes Secret and run `ldapsearch` against the principal:

```bash
PASS=$(kubectl get secret ldap-credentials \
  -n isvd-ldap \
  -o jsonpath='{.data.adminPassword}' | base64 -d)

# Search all users on the principal (NodePort 30389)
ldapsearch \
  -h <node-ip> -p 30389 \
  -D cn=root -w "$PASS" \
  -s sub \
  -b "ou=users,o=sample" \
  "(objectClass=inetOrgPerson)" uid cn mail
```

Expected output:

```
uid=dave,ou=users,o=sample
uid=eve,ou=users,o=sample
```

**Verify a specific user exists:**

```bash
ldapsearch \
  -h <node-ip> -p 30389 \
  -D cn=root -w "$PASS" \
  -s sub \
  -b "ou=users,o=sample" \
  "(uid=dave)" cn mail
```

**Check DN count on both nodes (replication parity):**

```bash
# Principal
ldapsearch -h <node-ip> -p 30389 \
  -D cn=root -w "$PASS" \
  -s sub -b "o=sample" "(objectClass=*)" dn \
  2>/dev/null | grep -c "="

# Replica-1
ldapsearch -h <node-ip> -p 31389 \
  -D cn=root -w "$PASS" \
  -s sub -b "o=sample" "(objectClass=*)" dn \
  2>/dev/null | grep -c "="
```

Both counts must be equal and non-zero.

> **IBM ISVD ldapsearch syntax note:** IBM ISVD ships its own LDAP tools — always use
> `-h <host> -p <port>` (not the OpenLDAP URI form `-H ldap://host:port`). The output contains
> raw DN values (e.g. `uid=dave,ou=users,o=sample`) without a `dn:` prefix, so count with
> `grep -c "="` rather than `grep -c "^dn:"`.

---

## Helm Test

Run the built-in DN count parity test to confirm replication is healthy:

```bash
helm test isvd-ldap -n isvd-ldap --logs
```

The test pod counts every DN under `o=sample` on the principal and each replica. It passes only
when all nodes have identical, non-zero counts.

```
────────────────────────────────────────
  ISVD LDAP DN Count Parity Test
────────────────────────────────────────
  PASS: ldap-principal has 4 DNs
  PASS: ldap-replica-1 DN count matches principal (4 = 4) — replication OK

────────────────────────────────────────
  Test Summary
────────────────────────────────────────
  Nodes checked : ldap-principal + 1 replica(s)
  Principal DNs : 4

  ALL DN COUNT TESTS PASSED — setup is working correctly.
```

---

## Re-seeding a Stale Replica

If a replica pod has been offline longer than `ldif.replicationPurgeWindowHours` (default 20 h)
the ISVD replication changelog on the principal may have been purged. The `staleness-check` init
container will block the replica from starting and print:

```
!! STALE REPLICA DETECTED !!
This replica's data is 25h old.
ACTION REQUIRED — reseed this replica from the current principal:
  cd /Users/suchi/projects/ibm-isvd/helm && helm upgrade isvd-ldap ./isvd-ldap \
    -f ./isvd-ldap/<values-test|values-prod>.yaml \
    --namespace isvd-ldap 2>&1
```

Running `helm upgrade` triggers the orchestrator again, which performs a fresh binary PVC seed
and writes a new `.seeded_at` timestamp, unblocking the replica.

---

## Uninstall

```bash
helm uninstall isvd-ldap -n isvd-ldap
```

> The `ldap-ldif-pvc` PVC is annotated with `helm.sh/resource-policy: keep` and will **not** be
> deleted. To remove it manually:
>
> ```bash
> kubectl delete pvc ldap-ldif-pvc -n isvd-ldap
> kubectl delete namespace isvd-ldap
> ```

