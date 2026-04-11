from flask import Blueprint, request, jsonify, current_app
from utils.did_utils import generate_did, is_valid_did, sanitize_did
from utils.qr_utils import generate_qr_base64

wallet_bp = Blueprint("wallet", __name__, url_prefix="/wallet")


# ── POST /wallet/create-did ───────────────────────────────────────────────────
#
# Generates a fresh DID. No parameters required.
# The DID is shown ONCE — it's the client's responsibility to save it.
#
# Response 200:
#   { "did": "did:decen:<hex>" }

@wallet_bp.route("/create-did", methods=["POST"])
def create_did():
    did = generate_did()
    return jsonify({
        "did":     did,
        "message": "Store this DID securely. It will not be shown again."
    }), 201


# ── GET /wallet/credentials?did=<did> ────────────────────────────────────────
#
# Returns all credentials issued under the given DID.
# No auth required — the DID itself is the access token.
#
# Response 200:
#   {
#     "status": "active" | "revoked" | "not_found",
#     "did": "...",
#     "credentials": [ { username, degree, expiry, verification_hash,
#                         issued_at, block_index, block_hash, hash_valid } ]
#     "revoke_info": { reason, revoked_at, block_hash }   ← only if revoked
#   }

@wallet_bp.route("/credentials", methods=["GET"])
def view_credentials():
    did = sanitize_did(request.args.get("did", ""))

    if not did:
        return jsonify({"error": "DID is required", "code": "MISSING_DID"}), 400

    if not is_valid_did(did):
        return jsonify({"error": "Invalid DID format", "code": "INVALID_DID"}), 422

    chain = current_app.config["BLOCKCHAIN"]
    result = chain.get_credentials_for_did(did)

    status_codes = {"not_found": 404, "revoked": 200, "active": 200}
    return jsonify(result), status_codes[result["status"]]


# ── GET /wallet/share?did=<did> ───────────────────────────────────────────────
#
# Returns a base64 QR code PNG pointing to /verify?did=<did>.
# Scanning the QR takes anyone to the public verification endpoint.
#
# Response 200:
#   { "did": "...", "qr_code": "data:image/png;base64,..." }

@wallet_bp.route("/share", methods=["GET"])
def share_qr():
    did = sanitize_did(request.args.get("did", ""))

    if not did:
        return jsonify({"error": "DID is required", "code": "MISSING_DID"}), 400

    if not is_valid_did(did):
        return jsonify({"error": "Invalid DID format", "code": "INVALID_DID"}), 422

    base_url = request.host_url.rstrip("/")
    qr_data_uri = generate_qr_base64(did, base_url)

    return jsonify({
        "did":      did,
        "qr_code":  qr_data_uri,
        "scan_url": f"{base_url}/verify?did={did}",
    }), 200
