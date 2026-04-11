import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Optional


# ─────────────────────────────────────────────
#  Block
# ─────────────────────────────────────────────

@dataclass
class Block:
    index: int
    timestamp: float
    block_type: str          # "GENESIS" | "CREDENTIAL" | "REVOKE"
    did: str
    data: dict               # credential payload or revoke note
    prev_hash: str
    nonce: int = 0
    hash: str = field(default="", init=False)

    def __post_init__(self):
        self.hash = self._compute_hash()

    def _compute_hash(self) -> str:
        payload = json.dumps({
            "index":      self.index,
            "timestamp":  self.timestamp,
            "block_type": self.block_type,
            "did":        self.did,
            "data":       self.data,
            "prev_hash":  self.prev_hash,
            "nonce":      self.nonce,
        }, sort_keys=True).encode()
        return hashlib.sha256(payload).hexdigest()

    def mine(self, difficulty: int = 3):
        target = "0" * difficulty
        while not self.hash.startswith(target):
            self.nonce += 1
            self.hash = self._compute_hash()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["hash"] = self.hash
        return d


# ─────────────────────────────────────────────
#  Blockchain
# ─────────────────────────────────────────────

class Blockchain:
    DIFFICULTY = 3

    def __init__(self, storage_path: str = "chain.json"):
        self.storage_path = storage_path
        self.chain: list[Block] = []
        self._load_or_init()

    # ── persistence ──────────────────────────

    def _load_or_init(self):
        try:
            with open(self.storage_path, "r") as f:
                raw = json.load(f)
            self.chain = [self._block_from_dict(b) for b in raw]
        except (FileNotFoundError, json.JSONDecodeError):
            genesis = Block(
                index=0,
                timestamp=time.time(),
                block_type="GENESIS",
                did="GENESIS",
                data={"note": "Genesis block"},
                prev_hash="0" * 64,
            )
            genesis.mine(0)
            self.chain = [genesis]
            self._save()

    def _save(self):
        with open(self.storage_path, "w") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2)

    @staticmethod
    def _block_from_dict(d: dict) -> Block:
        b = Block(
            index=d["index"],
            timestamp=d["timestamp"],
            block_type=d["block_type"],
            did=d["did"],
            data=d["data"],
            prev_hash=d["prev_hash"],
            nonce=d["nonce"],
        )
        b.hash = d["hash"]
        return b

    # ── helpers ───────────────────────────────

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    @staticmethod
    def compute_verification_hash(username: str, did: str) -> str:
        """
        SHA-256 of concatenated (username stripped of spaces) + did.
        e.g. "Alpha Beta" + "abc123" → SHA-256("AlphaBetaabc123")
        """
        raw = username.replace(" ", "") + did
        return hashlib.sha256(raw.encode()).hexdigest()

    # ── DID existence checks ──────────────────

    def did_exists(self, did: str) -> bool:
        """True if at least one CREDENTIAL block exists for this DID (not revoked)."""
        return self._get_did_status(did) == "active"

    def _get_did_status(self, did: str) -> str:
        """
        Returns:
            "not_found"  — no block with this DID at all
            "active"     — has credential block(s), not revoked
            "revoked"    — has been explicitly revoked
        """
        has_credential = False
        is_revoked = False

        for block in self.chain:
            if block.did == did:
                if block.block_type == "CREDENTIAL":
                    has_credential = True
                elif block.block_type == "REVOKE":
                    is_revoked = True

        if not has_credential:
            return "not_found"
        if is_revoked:
            return "revoked"
        return "active"

    # ── public API ────────────────────────────

    def issue_credential(
        self,
        did: str,
        username: str,
        degree: str,
        expiry: str,
    ) -> Block:
        """
        Adds a CREDENTIAL block. A DID can have multiple credentials
        (multiple achievements), each becomes its own block.
        """
        verification_hash = self.compute_verification_hash(username, did)
        data = {
            "username":          username,
            "degree":            degree,
            "expiry":            expiry,
            "verification_hash": verification_hash,
        }
        block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            block_type="CREDENTIAL",
            did=did,
            data=data,
            prev_hash=self.last_block.hash,
        )
        block.mine(self.DIFFICULTY)
        self.chain.append(block)
        self._save()
        return block

    def revoke_did(self, did: str, reason: str = "Revoked by issuer") -> Optional[Block]:
        """
        Appends a REVOKE block for the given DID.
        Returns None if DID was never found or already revoked.
        """
        status = self._get_did_status(did)
        if status != "active":
            return None

        block = Block(
            index=len(self.chain),
            timestamp=time.time(),
            block_type="REVOKE",
            did=did,
            data={"reason": reason},
            prev_hash=self.last_block.hash,
        )
        block.mine(self.DIFFICULTY)
        self.chain.append(block)
        self._save()
        return block

    def get_credentials_for_did(self, did: str) -> dict:
        """
        Returns a structured result for a DID:

        {
          "status": "not_found" | "revoked" | "active",
          "did": ...,
          "credentials": [...],   # list of all CREDENTIAL blocks for this DID
          "revoke_info": {...}     # present only if revoked
        }
        """
        status = self._get_did_status(did)
        credentials = []
        revoke_info = None

        for block in self.chain:
            if block.did != did:
                continue
            if block.block_type == "CREDENTIAL":
                entry = dict(block.data)
                entry["block_index"] = block.index
                entry["issued_at"] = block.timestamp
                entry["block_hash"] = block.hash
                # live hash check
                expected = self.compute_verification_hash(
                    entry["username"], did
                )
                entry["hash_valid"] = (entry["verification_hash"] == expected)
                credentials.append(entry)
            elif block.block_type == "REVOKE":
                revoke_info = {
                    "reason":     block.data.get("reason"),
                    "revoked_at": block.timestamp,
                    "block_hash": block.hash,
                }

        result = {
            "status":      status,
            "did":         did,
            "credentials": credentials,
        }
        if revoke_info:
            result["revoke_info"] = revoke_info

        return result

    def get_full_chain(self) -> list[dict]:
        return [b.to_dict() for b in self.chain]

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            curr = self.chain[i]
            prev = self.chain[i - 1]
            if curr.hash != curr._compute_hash():
                return False
            if curr.prev_hash != prev.hash:
                return False
        return True
