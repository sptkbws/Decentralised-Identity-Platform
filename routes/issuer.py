from flask import Blueprint, request, jsonify, current_app
from utils.did_utils import is_valid_did, sanitize_did

issuer_bp = Blueprint("issuer", __name__, url_prefix="/issuer")


# ── POST /issuer/issue ────────────────────────────────────────────────────────
#
# Issues a new credential block for a given DID.
# A DID can have multiple credentials (multiple achievements/degrees).
# Each call appends a new CREDENTIAL block to the chain.
#
# Request JSON:
#   {
#     "did":    "did:decen:<hex>",
#     "username": "Alpha Beta",
#     "degree": "B.Tech Computer Science",
#     "expiry": "2027-12-31"
#   }
#
# Response 201:
#   {
#     "message": "Credential issued",
#     "block": {
#       "index": 3,
#       "block_type": "CREDENTIAL",
#       "did": "...",
#       "data": { username, degree, expiry, verification_hash },
#       "hash": "...",
#       "nonce": 12345,
#       "timestamp": 1700000000.0
#     }
#   }

@issuer_bp.route("/issue", methods=["POST"])
def issue_credential():
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required", "code": "NO_BODY"}), 400

    did      = sanitize_did(body.get("did", ""))
    username = body.get("username", "").strip()
    degree   = body.get("degree", "").strip()
    expiry   = body.get("expiry", "").strip()

    # ── validation ────────────────────────────────────────────────────────────
    errors = {}
    if not did:
        errors["did"] = "DID is required"
    elif not is_valid_did(did):
        errors["did"] = "Invalid DID format"

    if not username:
        errors["username"] = "Username is required"

    if not degree:
        errors["degree"] = "Degree is required"

    if not expiry:
        errors["expiry"] = "Expiry date is required"

    if errors:
        return jsonify({"error": "Validation failed", "fields": errors}), 422

    # ── check DID is not revoked ───────────────────────────────────────────────
    chain  = current_app.config["BLOCKCHAIN"]
    status = chain._get_did_status(did)

    if status == "revoked":
        return jsonify({
            "error": "This DID has been revoked and cannot receive new credentials",
            "code":  "DID_REVOKED"
        }), 403

    # ── issue ─────────────────────────────────────────────────────────────────
    block = chain.issue_credential(
        did=did,
        username=username,
        degree=degree,
        expiry=expiry,
    )

    return jsonify({
        "message": "Credential issued and added to the chain",
        "block":   block.to_dict(),
    }), 201


# ── GET /issuer/chain ─────────────────────────────────────────────────────────
#
# Returns the full blockchain — used by the chain explorer UI.
# No auth required (read-only, public ledger by design).
#
# Response 200:
#   {
#     "length": 5,
#     "valid": true,
#     "chain": [ { ...block fields... }, ... ]
#   }

@issuer_bp.route("/chain", methods=["GET"])
def get_chain():
    chain = current_app.config["BLOCKCHAIN"]
    return jsonify({
        "length": chain.chain_length(),
        "valid":  chain.is_chain_valid(),
        "chain":  chain.get_full_chain(),
    }), 200


# ── GET /issuer/verify-hash?did=<did>&username=<name> ────────────────────────
#
# Utility endpoint: recomputes the verification hash so the frontend
# can show a live "hash preview" before submitting.
#
# Response 200:
#   { "verification_hash": "abc123...", "input": "AlphaBetadid:decen:..." }

@issuer_bp.route("/verify-hash", methods=["GET"])
def preview_hash():
    did      = sanitize_did(request.args.get("did", ""))
    username = request.args.get("username", "").strip()

    if not did or not username:
        return jsonify({"error": "did and username are required"}), 400

    chain = current_app.config["BLOCKCHAIN"]
    raw   = username.replace(" ", "") + did
    vh    = chain.compute_verification_hash(username, did)

    return jsonify({
        "verification_hash": vh,
        "input_string":      raw,
    }), 200