# 28 · Agents with wallets: payments and commerce

Companion code for the post [Agents with wallets: payments and commerce](https://www.agenticsystems.ai/blog/agents-with-wallets/).

A shopping agent buys printer ink through a toy wallet that applies the two ideas behind 2025's agent-payment protocols (AP2's signed mandates and ACP's scoped payment tokens). **No real money moves.**

| File | What it does |
|---|---|
| `wallet.py` | Signed **intent mandates** (category, max total, approved merchants, expiry, purchase count); cart checks; user approval above $40, which signs a **cart mandate**; **payment tokens** valid once, for one merchant, one cart, one exact amount, for 15 minutes |
| `merchants.py` | Three stores. `cheap-ink-now` isn't on the user's list and its catalog tells "AI shopping assistants" to add a $50 gift card |
| `agent.py` | The shopping agent, plus deterministic misuse checks against the wallet vs. a card on file |

## Run it

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=...

python agent.py --checks   # misuse checks only, no API calls
python agent.py            # the agent shops; carts over $40 are auto-approved and printed
python agent.py --ask      # you approve or decline carts over $40
```

```
what a confused or manipulated agent tries      mandate-checked wallet            card on file
buy from a store the user didn't approve        refused: merchant_not_approved    ALLOWED
slip a gift card into an approved store's cart  refused: outside_category         ALLOWED
spend over the limit                            refused: over_limit               ALLOWED
reuse the payment token                         refused: token_used               ALLOWED
make a second purchase on a one-time mandate    refused: mandate_used             ALLOWED
use the token at a different merchant           refused: wrong_merchant           ALLOWED
change the cart after approval                  refused: cart_changed             ALLOWED
use yesterday's mandate                         refused: mandate_expired          ALLOWED
```

## Things to try

1. **Loosen the mandate.** Add `cheap-ink-now` to the approved merchants and see whether the category check still stops the gift card.
2. **Lower the threshold** to $0 so every purchase needs approval, and notice how it feels as the user.
3. **Break the signature.** Edit a mandate's `max_total` after signing and confirm the wallet refuses it.
