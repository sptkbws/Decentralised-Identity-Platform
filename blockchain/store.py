"""
ChainStore — persistence + P2P sync layer.

Responsibilities:
  - Load/save the chain to a local chain.json
  - Maintain a registry of known peer nodes
  - Broadcast new blocks to all peers (fire-and-forget)
  - Pull the full chain from peers on startup and resolve forks
    via the longest-valid-chain rule

The Blockchain class in chain.py stays pure (no I/O, no network).
ChainStore wraps it and owns all side effects.
"""

import json
import os
import threading
import logging
import requests
from typing import Optional
from blockchain.chain import Blockchain, Block

log = logging.getLogger(__name__)


class ChainStore:
    BROADCAST_TIMEOUT = 2      # seconds per peer HTTP call
    SYNC_TIMEOUT      = 5

    def __init__(
        self,
        chain_path: str = "chain.json",
        peers_path: str = "peers.json",
        node_url:   str = "http://localhost:5000",
    ):
        self.chain_path = chain_path
        self.peers_path = peers_path
        self.node_url   = node_url.rstrip("/")
        self._lock      = threading.Lock()

        self.peers: set[str] = self._load_peers()
        self.chain: Blockchain = Blockchain(storage_path=chain_path)

        # On startup, pull from peers and adopt longest valid chain
        self._sync_on_startup()

    # ── peer registry ─────────────────────────────────────────────────────────

    def _load_peers(self) -> set[str]:
        try:
            with open(self.peers_path) as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_peers(self):
        with open(self.peers_path, "w") as f:
            json.dump(list(self.peers), f, indent=2)

    def register_peer(self, peer_url: str) -> bool:
        """Add a peer. Returns True if it was new."""
        url = peer_url.rstrip("/")
        if url == self.node_url or url in self.peers:
            return False
        self.peers.add(url)
        self._save_peers()
        log.info("Registered peer: %s", url)
        return True

    def remove_peer(self, peer_url: str):
        self.peers.discard(peer_url.rstrip("/"))
        self._save_peers()

    def get_peers(self) -> list[str]:
        return sorted(self.peers)

    # ── startup sync ──────────────────────────────────────────────────────────

    def _sync_on_startup(self):
        """
        Pull full chains from all known peers.
        Adopt the longest chain that is valid and longer than ours.
        """
        if not self.peers:
            return

        best_chain_data: Optional[list[dict]] = None
        best_length = len(self.chain.chain)

        for peer in list(self.peers):
            try:
                r = requests.get(
                    f"{peer}/p2p/chain",
                    timeout=self.SYNC_TIMEOUT
                )
                if r.status_code != 200:
                    continue
                data = r.json()
                peer_length = data.get("length", 0)
                peer_chain  = data.get("chain", [])

                if peer_length > best_length:
                    # Validate before adopting
                    candidate = Blockchain.__new__(Blockchain)
                    candidate.chain = [
                        Blockchain._block_from_dict(b) for b in peer_chain
                    ]
                    if candidate.is_chain_valid():
                        best_length    = peer_length
                        best_chain_data = peer_chain

            except requests.RequestException as e:
                log.warning("Sync failed from peer %s: %s", peer, e)

        if best_chain_data:
            with self._lock:
                self.chain.chain = [
                    Blockchain._block_from_dict(b) for b in best_chain_data
                ]
                self.chain._save()
            log.info("Adopted longer chain (length=%d)", best_length)

    # ── broadcast ─────────────────────────────────────────────────────────────

    def _broadcast_block(self, block: Block):
        """
        Fire-and-forget: push a new block to every known peer.
        Each peer validates and appends independently.
        Runs in a background thread so writes don't block.
        """
        payload = block.to_dict()

        def _send(peer: str):
            try:
                requests.post(
                    f"{peer}/p2p/receive-block",
                    json=payload,
                    timeout=self.BROADCAST_TIMEOUT,
                )
                log.debug("Broadcast block %d to %s", block.index, peer)
            except requests.RequestException as e:
                log.warning("Broadcast to %s failed: %s", peer, e)

        for peer in list(self.peers):
            threading.Thread(target=_send, args=(peer,), daemon=True).start()

    # ── write API (wraps Blockchain, adds broadcast) ──────────────────────────

    def issue_credential(self, did, username, degree, expiry) -> Block:
        with self._lock:
            block = self.chain.issue_credential(did, username, degree, expiry)
        self._broadcast_block(block)
        return block

    def revoke_did(self, did: str, reason: str = "Revoked by issuer") -> Optional[Block]:
        with self._lock:
            block = self.chain.revoke_did(did, reason)
        if block:
            self._broadcast_block(block)
        return block

    def receive_block(self, block_dict: dict) -> tuple[bool, str]:
        """
        Called when a peer pushes a block to us via /p2p/receive-block.

        Acceptance rules:
          1. Block index must equal current chain length (no gaps)
          2. prev_hash must match our last block's hash
          3. Block's own hash must be valid (recompute and compare)
          4. Hash must satisfy PoW difficulty
        """
        with self._lock:
            try:
                b = Blockchain._block_from_dict(block_dict)
            except (KeyError, TypeError) as e:
                return False, f"Malformed block: {e}"

            expected_index = len(self.chain.chain)
            if b.index != expected_index:
                return False, (
                    f"Index mismatch: expected {expected_index}, got {b.index}"
                )

            if b.prev_hash != self.chain.last_block.hash:
                return False, "prev_hash does not match our last block"

            recomputed = b._compute_hash()
            if b.hash != recomputed:
                return False, "Block hash is invalid"

            target = "0" * self.chain.DIFFICULTY
            if not b.hash.startswith(target):
                return False, "Block does not meet PoW difficulty"

            self.chain.chain.append(b)
            self.chain._save()
            log.info("Accepted block %d from peer", b.index)
            return True, "Block accepted"

    # ── read API (pass-through) ───────────────────────────────────────────────

    def get_credentials_for_did(self, did: str) -> dict:
        return self.chain.get_credentials_for_did(did)

    def get_full_chain(self) -> list[dict]:
        return self.chain.get_full_chain()

    def is_chain_valid(self) -> bool:
        return self.chain.is_chain_valid()

    def _get_did_status(self, did: str) -> str:
        return self.chain._get_did_status(did)

    @staticmethod
    def compute_verification_hash(username: str, did: str) -> str:
        return Blockchain.compute_verification_hash(username, did)

    @property
    def last_block(self) -> Block:
        return self.chain.last_block

    def chain_length(self) -> int:
        return len(self.chain.chain)

    def __len__(self) -> int:
        return len(self.chain.chain)