"""
P2P routes — internal endpoints used by nodes to talk to each other.

Endpoints:
  GET  /p2p/chain              — return full chain (for sync)
  POST /p2p/receive-block      — accept a pushed block from a peer
  GET  /p2p/peers              — list known peers
  POST /p2p/register-peer      — announce yourself to this node
  POST /p2p/sync               — trigger a manual sync from all peers
"""

from flask import Blueprint, request, jsonify, current_app

p2p_bp = Blueprint("p2p", __name__, url_prefix="/p2p")


# ── GET /p2p/chain ────────────────────────────────────────────────────────────
# Peer asks for our full chain so it can check if it's behind.

@p2p_bp.route("/chain", methods=["GET"])
def get_chain():
    store = current_app.config["STORE"]
    return jsonify({
        "length": store.chain_length(),
        "valid":  store.is_chain_valid(),
        "chain":  store.get_full_chain(),
        "node":   current_app.config["NODE_URL"],
    }), 200


# ── POST /p2p/receive-block ───────────────────────────────────────────────────
# A peer mined/issued a new block and is broadcasting it to us.

@p2p_bp.route("/receive-block", methods=["POST"])
def receive_block():
    block_dict = request.get_json(silent=True)
    if not block_dict:
        return jsonify({"error": "No block data"}), 400

    store = current_app.config["STORE"]
    accepted, message = store.receive_block(block_dict)

    if accepted:
        return jsonify({"status": "accepted", "message": message}), 200
    else:
        return jsonify({"status": "rejected", "message": message}), 409


# ── GET /p2p/peers ────────────────────────────────────────────────────────────

@p2p_bp.route("/peers", methods=["GET"])
def list_peers():
    store = current_app.config["STORE"]
    return jsonify({
        "node":  current_app.config["NODE_URL"],
        "peers": store.get_peers(),
    }), 200


# ── POST /p2p/register-peer ───────────────────────────────────────────────────
# A new node announces itself: { "url": "http://localhost:5002" }
# We add it to our peers list and optionally ping back to register ourselves.

@p2p_bp.route("/register-peer", methods=["POST"])
def register_peer():
    body = request.get_json(silent=True) or {}
    peer_url = body.get("url", "").strip().rstrip("/")

    if not peer_url:
        return jsonify({"error": "url is required"}), 400

    store    = current_app.config["STORE"]
    is_new   = store.register_peer(peer_url)

    return jsonify({
        "status":  "registered" if is_new else "already_known",
        "peer":    peer_url,
        "peers":   store.get_peers(),
    }), 200


# ── POST /p2p/sync ────────────────────────────────────────────────────────────
# Manually trigger a sync from all known peers.
# Useful after adding a new peer to immediately pull their chain.

@p2p_bp.route("/sync", methods=["POST"])
def manual_sync():
    store = current_app.config["STORE"]
    before = store.chain_length()
    store._sync_on_startup()           # reuse the same sync logic
    after  = store.chain_length()

    return jsonify({
        "status":        "synced",
        "chain_before":  before,
        "chain_after":   after,
        "adopted_blocks": after - before,
    }), 200
