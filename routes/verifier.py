from flask import Blueprint, request, jsonify, session, current_app
from utils.auth_db import login_required, authenticate_user, register_user
from utils.did_utils import is_valid_did, sanitize_did

verifier_bp = Blueprint("verifier", __name__, url_prefix="/verifier")


# ── POST /verifier/login ──────────────────────────────────────────────────────
#
# Authenticates a user and creates a session.
#
# Request JSON: { "username": "admin", "password": "admin123" }
# Response 200: { "message": "Logged in", "username": "admin" }
# Response 401: { "error": "Invalid credentials" }

@verifier_bp.route("/login", methods=["POST"])
def login():
    body = request.get_json(silent=True) or {}
    username = body.get("username", "").strip()
    password = body.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    db_path = current_app.config["AUTH_DB"]
    if not authenticate_user(db_path, username, password):
        return jsonify({"error": "Invalid credentials", "code": "BAD_CREDENTIALS"}), 401

    session["logged_in"] = True
    session["username"]  = username
    return jsonify({"message": "Logged in successfully", "username": username}), 200


# ── POST /verifier/logout ─────────────────────────────────────────────────────

@verifier_bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"message": "Logged out"}), 200


# ── GET /verifier/me ──────────────────────────────────────────────────────────

@verifier_bp.route("/me", methods=["GET"])
def me():
    if session.get("logged_in"):
        return jsonify({"logged_in": True, "username": session.get("username")}), 200
    return jsonify({"logged_in": False}), 200


# ── GET /verifier/lookup?did=<did> ───────────────────────────────────────────
#
# AUTH REQUIRED.
# Full credential lookup — returns active credentials, revoke info, hash validity.
# Three possible outcomes mapped to clear status strings:
#   "not_found" → 404
#   "revoked"   → 200 with revoke_info
#   "active"    → 200 with credentials list
#
# Response shape mirrors Blockchain.get_credentials_for_did()

@verifier_bp.route("/lookup", methods=["GET"])
@login_required
def lookup():
    did = sanitize_did(request.args.get("did", ""))

    if not did:
        return jsonify({"error": "DID is required", "code": "MISSING_DID"}), 400

    if not is_valid_did(did):
        return jsonify({"error": "Invalid DID format", "code": "INVALID_DID"}), 422

    chain  = current_app.config["BLOCKCHAIN"]
    result = chain.get_credentials_for_did(did)

    http_status = 404 if result["status"] == "not_found" else 200
    return jsonify(result), http_status


# ── POST /verifier/revoke ─────────────────────────────────────────────────────
#
# AUTH REQUIRED.
# Appends a REVOKE block for the given DID.
# The original credential blocks remain intact (append-only chain).
#
# Request JSON:
#   { "did": "did:decen:<hex>", "reason": "optional reason string" }
#
# Response 200: { "message": "DID revoked", "block": { ...revoke block... } }
# Response 404: { "error": "DID not found" }
# Response 409: { "error": "DID already revoked" }

@verifier_bp.route("/revoke", methods=["POST"])
@login_required
def revoke():
    body   = request.get_json(silent=True) or {}
    did    = sanitize_did(body.get("did", ""))
    reason = body.get("reason", "Revoked by issuer").strip()

    if not did:
        return jsonify({"error": "DID is required", "code": "MISSING_DID"}), 400

    if not is_valid_did(did):
        return jsonify({"error": "Invalid DID format", "code": "INVALID_DID"}), 422

    chain  = current_app.config["BLOCKCHAIN"]
    status = chain._get_did_status(did)

    if status == "not_found":
        return jsonify({"error": "DID not found on the chain", "code": "NOT_FOUND"}), 404

    if status == "revoked":
        return jsonify({"error": "DID is already revoked", "code": "ALREADY_REVOKED"}), 409

    block = chain.revoke_did(did, reason)
    return jsonify({
        "message": "DID successfully revoked",
        "block":   block.to_dict(),
    }), 200


# ── GET /verify?did=<did> ─────────────────────────────────────────────────────
#
# PUBLIC endpoint — no auth required.
# This is what the QR code points to.
# Returns credential info if active, revoke info if revoked, 404 if unknown.

@verifier_bp.route("/public-verify", methods=["GET"])
def public_verify():
    did = sanitize_did(request.args.get("did", ""))

    if not did:
        return jsonify({"error": "DID is required"}), 400

    if not is_valid_did(did):
        return jsonify({"error": "Invalid DID format"}), 422

    chain  = current_app.config["BLOCKCHAIN"]
    result = chain.get_credentials_for_did(did)

    # Strip sensitive internal fields for public consumption
    if result["status"] == "active":
        for cred in result.get("credentials", []):
            cred.pop("block_hash", None)

    http_status = 404 if result["status"] == "not_found" else 200
    return jsonify(result), http_status