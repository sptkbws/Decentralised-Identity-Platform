# Decentralized Identity System (DID)

A full-stack decentralized identity and credential management system built with Python and Flask. Academic credentials are issued and stored on a custom-built blockchain. Each node holds a full copy of the chain and syncs with peers via a gossip protocol. No external blockchain framework is used — the chain is implemented from scratch.

---

## What it does

The system has three functional modules accessible from the web UI:

**Wallet** — Generate a Decentralized Identifier (DID) in the format `did:decen:<64-hex>`. The DID is the user's identity token. View all credentials issued under a DID. Share credentials via a QR code that points to the public verification endpoint.

**Issuer** — Issue academic credentials (name, degree, expiry) to a DID. Each credential is mined as a block on the chain with Proof-of-Work. A DID can hold multiple credentials (multiple degrees or achievements). Each block stores a verification hash computed as `SHA-256(name_without_spaces + did)` for tamper detection. The chain explorer shows the live ledger.

**Details and Verification** — Login-gated section for authorized issuers. Look up any DID and see its full credential record with hash validity status. Revoke a DID by appending a REVOKE block — the original credential blocks remain intact (append-only). The system returns three distinct states: `active`, `revoked`, or `not_found`.

---

## Tech stack

| Layer | Choice | Reason |
|---|---|---|
| Backend | Python 3.12, Flask 3 | Lightweight, no ORM overhead |
| Blockchain | Custom (chain.py) | Built from scratch, no Web3/Ethereum |
| Chain storage | `chain.json` per node | Human-readable, fully decentralized |
| Auth storage | SQLite (`auth.db`) | Node-local, passwords off the public ledger |
| QR generation | `qrcode[pil]` | Generates base64 PNG served inline |
| Frontend | Vanilla JS + Jinja2 | No build step, no framework |

---

## Directory structure

```
did_system/
├── app.py                      # Flask factory, CLI entry point, route registration
├── requirements.txt            # flask, qrcode[pil], Pillow, requests
│
├── blockchain/
│   ├── __init__.py
│   ├── chain.py                # Block dataclass, Blockchain engine (mine, validate, persist)
│   └── store.py                # ChainStore — wraps Blockchain, adds P2P broadcast and sync
│
├── routes/
│   ├── __init__.py
│   ├── wallet.py               # /wallet/*   — create-did, credentials, share/QR
│   ├── issuer.py               # /issuer/*   — issue credential, chain explorer, hash preview
│   ├── verifier.py             # /verifier/* — login, logout, lookup, revoke
│   └── p2p.py                  # /p2p/*      — block receive, peer registry, manual sync
│
├── utils/
│   ├── __init__.py
│   ├── did_utils.py            # generate_did(), is_valid_did(), sanitize_did()
│   ├── auth_db.py              # SQLite user store, authenticate_user(), @login_required
│   └── qr_utils.py            # generate_qr_base64() — returns data:image/png;base64,...
│
├── templates/
│   └── index.html              # Single-page app shell — all three sections
│
├── static/
│   ├── css/
│   │   └── main.css            # Dark terminal theme, CSS variables, all component styles
│   └── js/
│       └── app.js              # SPA router, fetch-based API client, all page logic
│
├── chain.json                  # Generated on first run — the blockchain ledger
├── peers.json                  # Generated on first run — known peer node URLs
└── auth.db                     # Generated on first run — SQLite verifier user store
```

`chain.json` and `peers.json` are decentralized — every node holds its own copy and they stay in sync via P2P. `auth.db` is intentionally node-local and never replicated.

---

## Installation

```bash
git clone <repo>
cd did_system
pip install -r requirements.txt
```

Python 3.12+ required. No other services needed.

---

## Running a single node

```bash
python app.py
```

Default port is 5000. Open `http://localhost:5000` in the browser.

On first run, `chain.json`, `peers.json`, and `auth.db` are created automatically in the project directory. The default admin account is seeded into `auth.db`.

---

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `ADMIN_USER` | `admin` | Verifier admin username seeded on first run |
| `ADMIN_PASS` | `admin123` | Verifier admin password seeded on first run |
| `SECRET_KEY` | `os.urandom(32)` | Flask session secret. Set a fixed value in production. |

```bash
export ADMIN_USER=yourname
export ADMIN_PASS=yourpassword
python app.py
```

Note: `ADMIN_USER` and `ADMIN_PASS` are upserted into `auth.db` on every startup, so changing them and restarting takes effect immediately.

`SECRET_KEY` uses `os.urandom(32)` by default, which generates a new key each time the process starts. This is fine as long as the server is not restarted between a user logging in and making subsequent requests. For production, set a fixed `SECRET_KEY` environment variable.

---

## CLI arguments

```
python app.py [--port PORT] [--chain PATH] [--peers PATH] [--auth-db PATH] [--node-url URL]
```

| Argument | Default | Description |
|---|---|---|
| `--port` | `5000` | Port to listen on |
| `--chain` | `chain.json` | Path to the chain ledger file |
| `--peers` | `peers.json` | Path to the peers registry file |
| `--auth-db` | `auth.db` | Path to the SQLite auth database |
| `--node-url` | `http://localhost:<port>` | Public URL of this node, used in P2P announcements |

---

## Running multiple nodes (P2P)

Each node needs its own data files and a `--node-url` that other nodes can actually reach.

```bash
# Node A
python app.py --port 5000 \
              --chain node_a/chain.json \
              --peers node_a/peers.json \
              --auth-db node_a/auth.db \
              --node-url http://192.168.1.39:5000

# Node B (separate machine or separate terminal)
python app.py --port 5002 \
              --chain node_b/chain.json \
              --peers node_b/peers.json \
              --auth-db node_b/auth.db \
              --node-url http://192.168.1.45:5002
```

Register the nodes with each other (do this once):

```bash
curl -X POST http://192.168.1.39:5000/p2p/register-peer \
  -H 'Content-Type: application/json' \
  -d '{"url": "http://192.168.1.45:5002"}'

curl -X POST http://192.168.1.45:5002/p2p/register-peer \
  -H 'Content-Type: application/json' \
  -d '{"url": "http://192.168.1.39:5000"}'
```

After registration, any block written on one node is broadcast to all known peers. On startup, each node pulls from all peers and adopts the longest valid chain.

---

## API reference

### Wallet

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/wallet/create-did` | None | Generate a new DID |
| GET | `/wallet/credentials?did=` | None | Get all credentials for a DID |
| GET | `/wallet/share?did=` | None | Get QR code for a DID |

### Issuer

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/issuer/issue` | None | Issue a credential block |
| GET | `/issuer/chain` | None | Get full chain (chain explorer) |
| GET | `/issuer/verify-hash?did=&username=` | None | Preview verification hash |

### Verifier

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/verifier/login` | None | Authenticate and create session |
| POST | `/verifier/logout` | None | Clear session |
| GET | `/verifier/me` | None | Check session status |
| GET | `/verifier/lookup?did=` | Required | Full credential lookup |
| POST | `/verifier/revoke` | Required | Append a REVOKE block |

### P2P (internal)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/p2p/chain` | Return this node's full chain |
| POST | `/p2p/receive-block` | Accept a broadcast block from a peer |
| GET | `/p2p/peers` | List known peers |
| POST | `/p2p/register-peer` | Register a new peer `{"url": "..."}` |
| POST | `/p2p/sync` | Manually trigger sync from all peers |

### Utility

| Method | Endpoint | Description |
|---|---|---|
| GET | `/health` | Node status, chain length, peer count |
| GET | `/verify?did=` | Public credential verification (QR target) |

---

## Block structure

Every entry in `chain.json` follows this schema:

```json
{
  "index": 2,
  "timestamp": 1700000000.0,
  "block_type": "CREDENTIAL",
  "did": "did:decen:3f8a2b...",
  "data": {
    "username": "Alpha Beta",
    "degree": "B.Tech Computer Science",
    "expiry": "2028-06-30",
    "verification_hash": "sha256(AlphaBetadid:decen:3f8a2b...)"
  },
  "prev_hash": "000abc...",
  "nonce": 58291,
  "hash": "000def..."
}
```

`block_type` is one of `GENESIS`, `CREDENTIAL`, or `REVOKE`. The hash always starts with `000` (difficulty 3). The genesis block uses `timestamp: 0.0` so all nodes produce an identical genesis hash, enabling cross-node `prev_hash` validation.

---

## Verification hash

The verification hash stored in each credential block is:

```
SHA-256(username_without_spaces + did)
```

Example: username `Alpha Beta`, DID `did:decen:abc123` → `SHA-256("AlphaBetadid:decen:abc123")`.

At lookup time the hash is recomputed and compared against the stored value. A mismatch indicates the block data has been tampered with.

---

## Clearing the pycache

If you copy updated `.py` files into the project and changes do not take effect, Python may be loading stale compiled bytecode from `__pycache__`. Clear it with:

```bash
find . -name "*.pyc" -delete && find . -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null
```

Or use the included `pycache_clear.sh` if present.

---

## Known limitations and production checklist

- `SESSION_COOKIE_SECURE` is set to `False` — enable this and run behind HTTPS in production.
- Password hashing uses SHA-256. Replace with `bcrypt` or `argon2` before any public deployment.
- The P2P layer has no authentication — any node that knows your IP can push blocks. Add a shared secret or certificate pinning for a production network.
- `chain.json` has no size limit. Add pruning or archiving for long-running nodes.
- The `/verifier/register` endpoint for adding additional admin users exists in the codebase but is not yet exposed in the UI.
