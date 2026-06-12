# Smart Mirror — Router / Wi-Fi Setup Spec

**Who this is for:** whoever configures the shop's router (an IT person or installer).
**Goal in one sentence:** customer phones must be able to use the mirror, but must
**not** be able to see each other or poke at anything else.

This is a **store kiosk** that films a customer and sends the clip to *their own*
phone. Customer privacy is the top priority. Please follow this exactly — the one
rule in **Step 3** is the part that makes it both *work* and *stay safe*. Skipping
it either breaks the product or leaves customers' videos exposed.

> ⚠️ **Important context: this router has NO internet on purpose.** Don't try to
> "fix" the lack of internet. The only thing customer phones need to reach is the
> mirror — nothing else.

---

## What we're building (the picture)

```
            ┌─────────────────────── ROUTER (one box) ───────────────────────┐
            │                                                                 │
  Customer  │   GUEST Wi-Fi  ──(blocked)── GUEST Wi-Fi   ... all phones       │
  phones ───┼──▶ "ShopGuest"   each other   isolated from each other          │
            │       │                                                         │
            │       │  ONE allowed path: phones → mirror, port 8765 only      │
            │       ▼                                                         │
            │   MAIN Wi-Fi   ──▶  the MIRROR (Raspberry Pi)                    │
            │   "ShopMain"                                                     │
            └─────────────────────────────────────────────────────────────────┘
```

- **Phones** join the **Guest** Wi-Fi.
- **The mirror** sits on the **Main** Wi-Fi.
- Phones may reach **only** the mirror, and **only** on its one "door" (port `8765`).
- Phones may **not** reach: each other, the router's settings page, or anything
  else on the mirror.

---

## Step-by-step

### Step 1 — Create two Wi-Fi networks on the one router
Most business/prosumer routers can broadcast more than one Wi-Fi name at once
(often called "Guest Network", "SSID", or "VLAN").

| Network | Name (example) | Who joins it |
|--------|----------------|--------------|
| **Main** | `ShopMain` | The mirror only (staff devices, if any) |
| **Guest** | `ShopGuest` | Customer phones |

Both networks should use **WPA3** security (see Step 4) with a password.

### Step 2 — Turn ON phone-to-phone blocking (on the Guest network)
In the Guest network settings, enable the option usually called
**"Client Isolation"**, **"AP Isolation"**, or **"Allow guests to see each other: OFF"**.
This stops one customer's phone from reaching another customer's phone.

### Step 3 — Open exactly ONE path: phones → mirror, port 8765 ⭐ (the critical rule)
By default the Guest and Main networks are walled off from each other, so phones
**can't** reach the mirror and the product won't work. Add **one** firewall rule:

> **ALLOW** traffic **from** the Guest network **to** the mirror's IP address,
> **on TCP port 8765 only**. **DENY / DROP** everything else from Guest to Main.

- **Source:** Guest network (the whole guest subnet)
- **Destination:** the mirror's IP address (see Step 5 — give it a fixed address)
- **Port / Protocol:** **TCP 8765 only**
- **Everything else Guest → Main:** **blocked**

Keep this window **narrow**. Do **not** use "allow Guest to access the local
network" (that's too wide — it would let phones reach everything). It must be
*this one device, this one port.*

### Step 4 — Use WPA3 (not WPA2) on both networks
Set the Wi-Fi security type to **WPA3** (sometimes shown as "WPA3-Personal" or
"WPA3-SAE"). If the router only offers "WPA2/WPA3 mixed", that's acceptable but
prefer **WPA3-only** if the customer phones support it.
*Why:* on the older WPA2, a customer who has the Wi-Fi password could eavesdrop on
another customer's video over the air. WPA3 stops that.

### Step 5 — Give the mirror a fixed (reserved) IP address
On the Main network, reserve a **static / fixed IP** for the mirror (DHCP
reservation tied to the mirror's hardware/MAC address).
*Why:* the rule in Step 3 and the QR-code links both point at the mirror's
address. If that address changes on its own, sessions and QR logins break.

### Step 6 — Lock down the router and the mirror
- **Change the default router admin password.** Customers must **not** be able to
  open the router's settings page from the Guest network.
- The mirror's own firewall should already **allow only TCP 8765** from the guest
  subnet and block everything else (no remote login exposed to customers).
- Since there are no automatic security updates (no internet), plan to apply
  offline updates to the router and the mirror periodically.

---

## How to verify it's set up correctly

Do these checks with a test phone on the **Guest** Wi-Fi.

**✅ Must WORK (the product):**
1. Scan the QR code on the mirror → the phone opens the login page.
2. Complete a session → record a clip → the clip appears on the phone and downloads.

**🚫 Must FAIL (the safety net) — if any of these *succeed*, the setup is wrong:**
3. From the test phone, try to open the **router's admin page** → should **fail**.
4. Put a **second** phone on Guest Wi-Fi; from phone A, try to reach phone B
   (e.g. ping its IP) → should **fail**.
5. Try to reach the mirror on a **different** port (e.g. its login port 22) →
   should **fail**. Only port 8765 should respond.
6. A device that is **not** on the Wi-Fi at all should reach **nothing**.

If checks 1–2 pass and 3–6 all fail, the network is correct.

---

## Quick fallbacks (if the router can't do Step 3)

Cheaper home routers often **can't** make that one narrow window — they're
all-or-nothing. If so, two alternatives still protect customer videos:

- **Option B — the mirror hosts its own Wi-Fi.** Phones connect directly to the
  mirror; turn on client isolation. Simpler, but puts more security load on the
  mirror itself. *(Discuss with the developer before choosing this.)*
- **Option C — one shared Wi-Fi + turn on in-app encryption (TLS).** The video is
  sealed end-to-end regardless of the network. The trade-off is a one-time
  "are you sure / not secure" warning on each customer's phone. *(The developer
  enables this with a single setting — ask for it.)*

---

## One-line summary for the installer

> Two Wi-Fi networks on the router (WPA3). Customer phones on an **isolated Guest**
> network. **Allow Guest → mirror IP : TCP 8765 only**; block everything else.
> Mirror gets a **fixed IP**. Change the router admin password.
