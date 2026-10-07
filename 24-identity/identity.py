"""A toy identity provider: agent identities, user grants, and delegated, scoped, short-lived tokens.

Tokens are signed JSON (JWT-style, HMAC-SHA256), so the example has no dependencies. Real systems use an OAuth 2.1
authorization server, signed JWTs and workload identity; the claims and the checks are the same ideas:

  sub    the user the agent acts for          act    the agent doing the acting (RFC 8693's "act" claim)
  aud    the one service the token is for      scope  what it may do there
  exp    a few minutes from now                jti    a unique id, so every action can be traced to one grant
  authorization_details   finer limits inside a scope, such as who mail may go to (RFC 9396)
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

_KEY = secrets.token_bytes(32)  # the provider's signing key; services trust tokens it signed

# Registered agents: each has its own identity and a ceiling on what it may ever be granted.
AGENTS = {"scheduling-agent": {"secret": secrets.token_hex(16), "max_scopes": {"calendar.read", "calendar.write", "mail.send"}}}
# What each user has allowed each agent to do on their behalf (the consent screen, in real life).
GRANTS = {("alice", "scheduling-agent"): {"calendar.read", "calendar.write", "mail.send"}}
TOKEN_LIFETIME = 300  # seconds


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def sign(claims: dict) -> str:
    body = _b64(json.dumps(claims, sort_keys=True).encode())
    return body + "." + _b64(hmac.new(_KEY, body.encode(), hashlib.sha256).digest())


def verify(token: str) -> dict:
    try:
        body, sig = token.split(".")
    except ValueError:
        raise PermissionError("malformed token")
    if not hmac.compare_digest(sig, _b64(hmac.new(_KEY, body.encode(), hashlib.sha256).digest())):
        raise PermissionError("bad_signature")
    claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    if claims["exp"] < time.time():
        raise PermissionError("expired: token lifetime is over")
    return claims


def delegate(user: str, agent: str, agent_secret: str, audience: str, scopes: set[str], task: str,
             details: list[dict] | None = None) -> str:
    """Token exchange: the agent proves its own identity, names the user, the one service, and the scopes this task
    needs. It gets back the intersection of what was asked, what the user granted, and the agent's ceiling."""
    reg = AGENTS.get(agent)
    if reg is None or not hmac.compare_digest(reg["secret"], agent_secret):
        raise PermissionError(f"bad_agent_credentials: {agent}")
    allowed = scopes & GRANTS.get((user, agent), set()) & reg["max_scopes"]
    allowed = {s for s in allowed if s.startswith(audience + ".")}
    if not allowed:
        raise PermissionError(f"not_granted: {agent} may not act for {user} on {audience} with {sorted(scopes)}")
    now = int(time.time())
    claims = {"sub": user, "act": {"sub": agent}, "aud": audience, "scope": " ".join(sorted(allowed)),
              "iat": now, "exp": now + TOKEN_LIFETIME, "jti": secrets.token_hex(6), "task": task}
    if details:
        claims["authorization_details"] = details
    return sign(claims)


# The anti-pattern, for comparison: one long-lived key that can do anything, anywhere, for anyone.
SHARED_KEY = sign({"sub": "service-account", "aud": "*", "scope": "*", "exp": int(time.time()) + 10 ** 9, "jti": "shared"})
