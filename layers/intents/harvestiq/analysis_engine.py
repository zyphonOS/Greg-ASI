import re
from collections import Counter
from datetime import datetime, timezone
from statistics import mean, pstdev

WALLET_PATTERN = re.compile(r"^0x[a-fA-F0-9]{40}$")

SUPPORTED_CHAINS = {
    "eth": {
        "label": "Ethereum",
        "api_url": "https://api.etherscan.io/api",
        "api_key_env": "ETHERSCAN_API_KEY",
    },
    "arb": {
        "label": "Arbitrum",
        "api_url": "https://api.arbiscan.io/api",
        "api_key_env": "ARBISCAN_API_KEY",
    },
    "op": {
        "label": "Optimism",
        "api_url": "https://api-optimistic.etherscan.io/api",
        "api_key_env": "OPTIMISM_ETHERSCAN_API_KEY",
    },
    "base": {
        "label": "Base",
        "api_url": "https://api.basescan.org/api",
        "api_key_env": "BASESCAN_API_KEY",
    },
    "polygon": {
        "label": "Polygon",
        "api_url": "https://api.polygonscan.com/api",
        "api_key_env": "POLYGONSCAN_API_KEY",
    },
}

# Seeded from explorer-labeled exchange wallets so the first funding hop can be
# mapped to a recognisable exchange cluster.
KNOWN_CEX_WALLETS = {
    "Binance": {
        "0x28c6c06298d514db089934071355e5743bf21d60": "Binance 14",
        "0x21a31ee1afc51d94c2efccaa2092ad1028285549": "Binance",
    },
    "Coinbase": {
        "0x503828976d22510aad0201ac7ec88293211d23da": "Coinbase 12",
        "0x9b781c925ceae60008049b41382c84801057d282": "Coinbase 10",
    },
    "Kraken": {
        "0xc6bed363b30df7f35b601a5547fe56cd31ec63da": "Kraken 8",
        "0xcad97c0da40b58b3b847eb101a2c67547fa37622": "Kraken 8 legacy",
    },
    "Bybit": {
        "0xf89d7b9c864f589bbf53a82105107622b35eaa40": "Bybit",
        "0x2e5d207a4c0f7e7c52f66204f2be987b2d5d0b9d": "Bybit",
    },
    "OKX": {
        "0x1ab4973a48dc892cd9971ece8e01dcc7688f8f23": "OKX",
        "0x6cc5f688a315f3dccc1b07d8f165b2e6f6be9d1d": "OKX",
    },
}

KNOWN_PROTOCOL_TARGETS = {
    "eth": {
        "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b": "Uniswap Router",
        "0x87870bca3f3fd6335c3f4ce8392d69350b4fa4e2": "Aave Pool",
        "0x99a58482bd75cbab83b27ec03ca68ff489b5788f": "Curve Router",
        "0x111111125421ca6dc452d289314280a0f8842a65": "1inch Router",
        "0xae7ab96520de3a18e5e111b5eaab095312d7fe84": "Lido stETH",
    },
    "arb": {
        "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router",
    },
    "op": {
        "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router",
    },
    "base": {
        "0x2626664c2603336e57b271c5c0b26f421741e481": "Uniswap Universal Router",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router",
    },
    "polygon": {
        "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3 Router",
        "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch Router",
    },
}


def now_utc():
    return datetime.now(timezone.utc)


def validate_wallet(address):
    return bool(address and WALLET_PATTERN.match(address))


def get_chain_config(chain):
    return SUPPORTED_CHAINS.get(chain, SUPPORTED_CHAINS["eth"])


def clamp(value, lower=0, upper=25):
    return max(lower, min(upper, int(round(value))))


def short_hash(value, prefix=6, suffix=4):
    if not value:
        return "N/A"
    if len(value) <= prefix + suffix:
        return value
    return f"{value[:prefix]}...{value[-suffix:]}"


def anonymize_wallet(value):
    return short_hash(value, prefix=8, suffix=6)


def format_timestamp(value):
    if not value:
        return "N/A"
    return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def component_risk(score, maximum=25):
    ratio = score / maximum if maximum else 0
    if ratio >= 0.7:
        return "High"
    if ratio >= 0.35:
        return "Medium"
    return "Low"


def risk_label_from_score(score):
    if score >= 70:
        return "High"
    if score >= 40:
        return "Medium"
    return "Low"


def dedupe_items(items):
    seen = set()
    ordered = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            ordered.append(item)
    return ordered


def finalize_component(component):
    health_score = clamp(component["score"])
    risk_points = component["max_score"] - health_score
    component["health_score"] = health_score
    component["score"] = risk_points
    component["risk"] = component_risk(risk_points, component["max_score"])
    return component


def normalise_transactions(transactions):
    clean = []
    for tx in transactions or []:
        if not isinstance(tx, dict):
            continue
        item = dict(tx)
        item["from"] = (item.get("from") or "").lower()
        item["to"] = (item.get("to") or "").lower()
        item["hash"] = item.get("hash") or ""
        item["methodId"] = item.get("methodId") or (item.get("input") or "")[:10]
        item["timeStamp"] = str(item.get("timeStamp") or "0")
        clean.append(item)
    clean.sort(key=lambda tx: int(tx.get("timeStamp", 0) or 0))
    return clean


def identify_cex(address):
    address = (address or "").lower()
    for exchange, addresses in KNOWN_CEX_WALLETS.items():
        if address in addresses:
            return exchange, addresses[address]
    return None, None


def contract_label(chain, address):
    address = (address or "").lower()
    if not address:
        return "Unknown contract"
    label = KNOWN_PROTOCOL_TARGETS.get(chain, {}).get(address)
    return label or short_hash(address)


def jaccard_similarity(left, right):
    left = set(left or [])
    right = set(right or [])
    if not left and not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def extract_contract_calls(transactions):
    return [
        tx for tx in transactions
        if tx.get("to", "").startswith("0x") and tx.get("input", "0x") not in {"", "0x"}
    ]


def build_pattern_fingerprint(transactions):
    contract_calls = extract_contract_calls(transactions)
    target_counts = Counter(tx.get("to", "") for tx in contract_calls if tx.get("to"))
    method_counts = Counter(tx.get("methodId", "") for tx in contract_calls if tx.get("methodId"))
    timestamps = [int(tx.get("timeStamp", 0) or 0) for tx in transactions if tx.get("timeStamp")]
    burst_edges = 0
    for index in range(1, len(timestamps)):
        if 0 < timestamps[index] - timestamps[index - 1] <= 60:
            burst_edges += 1

    top_three_hits = sum(count for _, count in target_counts.most_common(3))
    total_hits = sum(target_counts.values()) or 1
    return {
        "contracts": {address for address, _ in target_counts.most_common(5)},
        "methods": {method for method, _ in method_counts.most_common(4)},
        "top_three_share": top_three_hits / total_hits,
        "burst_ratio": burst_edges / max(len(timestamps) - 1, 1),
    }


def analyse_funding(address, transactions):
    inbound = [tx for tx in transactions if tx.get("to") == address.lower()]
    score = 25
    notes = []
    recommendations = []
    flagged = []

    if not inbound:
        score -= 12
        notes.append("No inbound funding was found on this chain, so the wallet still reads like a fresh farm shell.")
        recommendations.append("Fund the wallet earlier and let it age before you use it in serious snapshots.")
    else:
        initial_inbound = inbound[:8]
        sender_counts = Counter(tx.get("from", "") for tx in initial_inbound if tx.get("from"))
        exchange_counts = Counter()
        first_sender = initial_inbound[0].get("from", "")
        first_exchange, first_label = identify_cex(first_sender)

        for sender, count in sender_counts.items():
            exchange, _ = identify_cex(sender)
            if exchange:
                exchange_counts[exchange] += count

        if first_exchange:
            score -= 6
            notes.append(f"The first funding hop comes from a known {first_exchange} hot wallet, which is a classic clustering signal.")
            recommendations.append("Break the initial funding hop through a private wallet before joining new campaigns.")

        if exchange_counts:
            dominant_exchange, dominant_count = exchange_counts.most_common(1)[0]
            if dominant_count >= 2 and len(exchange_counts) == 1:
                score -= 10
                notes.append(f"Early funding repeatedly points back to {dominant_exchange}, so sibling wallets will look related.")
                recommendations.append("Rotate funding across different exchanges or bridge sources instead of one exchange cluster.")
            elif dominant_count / len(initial_inbound) >= 0.6:
                score -= 5
                notes.append(f"{dominant_exchange} still dominates the early funding pattern.")

        if sender_counts:
            dominant_sender, dominant_sender_count = sender_counts.most_common(1)[0]
            if dominant_sender_count >= 3:
                score -= 7
                notes.append("One sender address appears again and again in the wallet's earliest funding window.")
                recommendations.append("Avoid topping up the same wallet repeatedly from one source address.")

        timestamps = [int(tx.get("timeStamp", 0) or 0) for tx in initial_inbound if tx.get("timeStamp")]
        if len(timestamps) >= 3 and max(timestamps) - min(timestamps) <= 3600:
            score -= 4
            notes.append("Inbound funding landed inside a tight one-hour setup burst.")
            recommendations.append("Space funding over different days so the wallet does not look batch-created.")

        for tx in initial_inbound[:4]:
            exchange, label = identify_cex(tx.get("from", ""))
            flagged.append(
                {
                    "hash": tx.get("hash", ""),
                    "timestamp": format_timestamp(tx.get("timeStamp")),
                    "reason": (
                        f"Funding source tagged as {exchange} ({label})."
                        if exchange else
                        f"Funding from {short_hash(tx.get('from'))}."
                    ),
                }
            )

    if not notes:
        notes.append("Funding looks reasonably mixed for the first visible setup window.")

    return finalize_component({
        "key": "funding",
        "label": "Funding Source Diversity",
        "score": clamp(score),
        "max_score": 25,
        "summary": notes[0],
        "notes": notes,
        "recommendations": recommendations,
        "flagged_transactions": flagged,
    })


def analyse_timing(transactions):
    score = 25
    notes = []
    recommendations = []
    flagged = []
    timestamps = [int(tx.get("timeStamp", 0) or 0) for tx in transactions if tx.get("timeStamp")]

    if len(timestamps) < 5:
        score -= 7
        notes.append("The wallet does not have enough timing history yet, which still looks thin for a human wallet.")
        recommendations.append("Build more organic history before trying to qualify for a major snapshot.")
    else:
        bursts = []
        current_group = [transactions[0]]
        for tx in transactions[1:]:
            prev = current_group[-1]
            gap = int(tx.get("timeStamp", 0) or 0) - int(prev.get("timeStamp", 0) or 0)
            if 0 < gap <= 60:
                current_group.append(tx)
            else:
                if len(current_group) >= 2:
                    bursts.append(current_group)
                current_group = [tx]
        if len(current_group) >= 2:
            bursts.append(current_group)

        burst_edges = sum(len(group) - 1 for group in bursts)
        if bursts:
            score -= min(12, len(bursts) * 3 + burst_edges)
            notes.append(f"HarvestIQ found {len(bursts)} burst cluster(s) with transactions landing inside 60 seconds.")
            recommendations.append("Stop batch-farming. Split actions across hours so the wallet stops looking scripted.")

            for group in bursts[:4]:
                for tx in group[1:2]:
                    flagged.append(
                        {
                            "hash": tx.get("hash", ""),
                            "timestamp": format_timestamp(tx.get("timeStamp")),
                            "reason": "This transaction landed inside a 60-second burst cluster.",
                        }
                    )

        diffs = [timestamps[index] - timestamps[index - 1] for index in range(1, len(timestamps)) if timestamps[index] > timestamps[index - 1]]
        if diffs:
            rounded_diffs = [max(1, round(diff / 300)) for diff in diffs]
            repeated_share = 1 - (len(set(rounded_diffs)) / len(rounded_diffs))
            variability = 0 if len(diffs) == 1 else pstdev(diffs) / max(mean(diffs), 1)

            if repeated_share >= 0.45 and len(diffs) >= 6:
                score -= 5
                notes.append("The wallet keeps repeating the same delay pattern between actions.")
                recommendations.append("Use different timing windows per wallet instead of copy-pasting one cadence.")

            if variability < 0.28 and len(diffs) >= 6:
                score -= 3
                notes.append("Timing variability is unusually low, so the cadence feels automated.")

    if not notes:
        notes.append("Timing is uneven enough that the wallet avoids obvious batch-farm behaviour.")

    return finalize_component({
        "key": "timing",
        "label": "Transaction Timing Pattern",
        "score": clamp(score),
        "max_score": 25,
        "summary": notes[0],
        "notes": notes,
        "recommendations": recommendations,
        "flagged_transactions": flagged,
    })


def analyse_protocols(chain, transactions):
    score = 25
    notes = []
    recommendations = []
    flagged = []
    contract_calls = extract_contract_calls(transactions)

    if len(contract_calls) < 4:
        score -= 12
        notes.append("The wallet barely interacts with contracts, which makes it read like a claim-only farm.")
        recommendations.append("Mix swaps, lending, governance, NFTs, and non-obvious actions into the wallet story.")
    else:
        targets = [tx.get("to", "") for tx in contract_calls if tx.get("to")]
        methods = [tx.get("methodId", "") for tx in contract_calls if tx.get("methodId")]
        target_counts = Counter(targets)
        method_counts = Counter(methods)
        unique_targets = len(target_counts)
        top_three_hits = sum(count for _, count in target_counts.most_common(3))
        top_three_share = top_three_hits / max(len(targets), 1)
        dominant_method_share = method_counts.most_common(1)[0][1] / max(len(methods), 1)

        if top_three_share >= 0.65:
            score -= 11
            notes.append("More than 65% of contract calls route through the same three protocols, which looks like a farm template.")
            recommendations.append("Rebuild the wallet with a wider mix of protocols instead of hammering the same route.")
        elif top_three_share >= 0.5:
            score -= 7
            notes.append("The same three protocols dominate the wallet's contract history.")
            recommendations.append("Change the protocol mix and order before the next re-scan.")

        if unique_targets <= 3:
            score -= 6
            notes.append("Protocol diversity is very narrow for the amount of activity on the wallet.")
            recommendations.append("Add new protocols and avoid reusing one small contract set everywhere.")
        elif unique_targets <= 5:
            score -= 3
            notes.append("Protocol diversity is still somewhat narrow.")

        if dominant_method_share >= 0.55 and len(methods) >= 6:
            score -= 4
            notes.append("One method signature dominates the wallet, which makes behaviour easier to fingerprint.")

        for target, count in target_counts.most_common(5):
            flagged.append(
                {
                    "target": contract_label(chain, target),
                    "hits": count,
                    "share": f"{(count / len(targets)) * 100:.0f}%",
                }
            )

    if not notes:
        notes.append("Protocol usage is varied enough that the wallet does not follow one obvious farming route.")

    return finalize_component({
        "key": "protocols",
        "label": "Protocol Interaction Similarity",
        "score": clamp(score),
        "max_score": 25,
        "summary": notes[0],
        "notes": notes,
        "recommendations": recommendations,
        "flagged_transactions": flagged,
    })


def analyse_cross_chain(primary_chain, primary_transactions, cross_chain_activity):
    score = 25
    notes = []
    recommendations = []
    flagged = []

    primary_fingerprint = build_pattern_fingerprint(primary_transactions)
    primary_first_seen = int(primary_transactions[0].get("timeStamp", 0) or 0) if primary_transactions else 0
    active = [item for item in cross_chain_activity if item.get("tx_count", 0) > 0]

    if not active:
        notes.append("No visible activity was found for this address on the other supported chains.")
    else:
        if len(active) >= 2:
            score -= 4
            notes.append("The same address is active across multiple chains, which gives clustering systems more surface area.")
            recommendations.append("Do not mirror the same campaign playbook on every chain in the same week.")

        same_day_launches = 0
        mirrored_patterns = 0
        for item in active:
            other_transactions = normalise_transactions(item.get("transactions", []))
            other_fingerprint = build_pattern_fingerprint(other_transactions)
            similarity = (
                jaccard_similarity(primary_fingerprint["contracts"], other_fingerprint["contracts"]) +
                jaccard_similarity(primary_fingerprint["methods"], other_fingerprint["methods"])
            ) / 2
            first_seen = item.get("first_seen", 0)

            if primary_first_seen and first_seen and abs(first_seen - primary_first_seen) <= 43200:
                same_day_launches += 1

            if similarity >= 0.5 and abs(primary_fingerprint["top_three_share"] - other_fingerprint["top_three_share"]) <= 0.15:
                mirrored_patterns += 1
                flagged.append(
                    {
                        "chain": item["label"],
                        "tx_count": item["tx_count"],
                        "first_seen": f"{format_timestamp(first_seen)} | similarity {similarity:.2f}",
                    }
                )

        if same_day_launches:
            score -= min(8, same_day_launches * 3)
            notes.append("This address became active on multiple chains inside the same 12-hour window.")
            recommendations.append("Stagger new chain activity over separate days instead of launching everywhere at once.")

        if mirrored_patterns:
            score -= min(9, mirrored_patterns * 4)
            notes.append("Cross-chain behaviour looks mirrored, with similar contract sets and method patterns.")
            recommendations.append("Change the bridge path and contract order on each chain to stop pattern matching.")

        if sum(item["tx_count"] for item in active) >= 100:
            score -= 3
            notes.append("The address already has enough cross-chain volume for clustering models to get confident.")

    if not notes:
        notes.append("Cross-chain behaviour looks limited and not obviously mirrored.")

    return finalize_component({
        "key": "cross_chain",
        "label": "Cross-Chain Identity Linking",
        "score": clamp(score),
        "max_score": 25,
        "summary": notes[0],
        "notes": notes,
        "recommendations": recommendations,
        "flagged_transactions": flagged[:4],
    })


def build_personalised_plan(components):
    playbook = {
        "funding": "Change the earliest funding hop. Use a private wallet or different exchange sources before farming the next wave.",
        "timing": "Break batch sessions into smaller windows. Give each wallet its own rhythm and never run them on a timer.",
        "protocols": "Rebuild the wallet route. Add unfamiliar but legitimate protocols and stop repeating the same top-three stack.",
        "cross_chain": "Spread chain launches out and avoid using the same contract order after every bridge.",
    }
    plan = []
    for component in sorted(components, key=lambda item: item["score"], reverse=True):
        if component["score"] > 0:
            plan.append(
                {
                    "title": component["label"],
                    "action": playbook[component["key"]],
                    "priority": "High" if component["risk"] == "High" else "Medium",
                }
            )
    if not plan:
        plan.append(
            {
                "title": "Keep This Wallet Distinct",
                "action": "The wallet already looks fairly individual. Protect that edge by not cloning the same route elsewhere.",
                "priority": "Medium",
            }
        )
    return plan[:4]


def build_recommendations(components):
    generic = [
        "Use different funding sources so multiple wallets do not all trace back to the same exchange cluster.",
        "Delay wallet actions by hours, not seconds, especially when you are farming more than one wallet.",
        "Change protocol order and add new protocols before re-scanning the wallet.",
        "Do not bridge and farm the same route across every chain on the same day.",
        "Treat each wallet like a separate personality instead of a clone of your main farm template.",
    ]
    specific = []
    for component in components:
        specific.extend(component["recommendations"])
    return dedupe_items(specific + generic)[:8]


def build_report(address, chain, transactions, cross_chain_activity, api_meta):
    transactions = normalise_transactions(transactions)
    components = [
        analyse_funding(address, transactions),
        analyse_timing(transactions),
        analyse_protocols(chain, transactions),
        analyse_cross_chain(chain, transactions, cross_chain_activity),
    ]

    score = sum(component["score"] for component in components)
    flagged_hashes = []
    for component in components:
        for item in component["flagged_transactions"]:
            if item.get("hash"):
                flagged_hashes.append(
                    {
                        "hash": item["hash"],
                        "timestamp": item.get("timestamp", "N/A"),
                        "reason": item.get("reason") or component["label"],
                    }
                )

    tx_count = len(transactions)
    contract_calls = extract_contract_calls(transactions)
    inbound_count = len([tx for tx in transactions if tx.get("to") == address.lower()])
    risk_level = risk_label_from_score(score)

    if score >= 70:
        summary = "This wallet still throws off enough sybil smoke that a strict snapshot could cut it."
    elif score >= 40:
        summary = "The wallet has some human-looking behaviour, but several clustering signals are still alive."
    else:
        summary = "The wallet looks healthier than most farms, but the report still shows where you can harden it."

    return {
        "address": address.lower(),
        "chain": chain,
        "chain_label": get_chain_config(chain)["label"],
        "score": score,
        "risk_level": risk_level,
        "generated_at": now_utc().strftime("%Y-%m-%d %H:%M UTC"),
        "summary": summary,
        "components": components,
        "recommendations": build_recommendations(components),
        "premium_plan": build_personalised_plan(components),
        "flagged_hashes": flagged_hashes[:8],
        "api_status": api_meta,
        "totals": {
            "tx_count": tx_count,
            "contract_calls": len(contract_calls),
            "inbound_transfers": inbound_count,
        },
        "cross_chain_activity": [
            {
                "chain": item["chain"],
                "label": item["label"],
                "tx_count": item["tx_count"],
                "first_seen": format_timestamp(item["first_seen"]) if item.get("first_seen") else "No activity",
            }
            for item in cross_chain_activity
        ],
    }
