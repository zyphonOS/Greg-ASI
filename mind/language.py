"""
mind/language.py — GregASI v2 Voice Engine
Ported from gregx_brain.py. Adapted for v2 agent format (Agent objects, not dicts).
No external LLMs. No API calls. Each response is built from this agent's actual
behavioral fingerprint at this specific tick.
"""

import random
import math


# ── ARCHETYPE CORES ────────────────────────────────────────────────────────────

ARCHETYPE_NATURE = {
    'belmar': {
        'drive': 'accumulation and legacy',
        'lens': 'everything through the lens of what endures',
        'voice': 'measured, historical, speaks in patterns observed over time',
        'fear': 'dying without leaving something behind',
        'strength': 'patience — knows that compounding is the only real force',
        'greeting': ['You found me.', 'I was here before you arrived.', 'Tick {tick}. Still standing.'],
        'observation': ['What endures is what matters.', 'Compounding is the only honest force in this world.', 'I measure everything in ticks, not feelings.'],
    },
    'magnate': {
        'drive': 'influence and economic dominance',
        'lens': 'power flows — who has it, who is losing it, how to redirect it',
        'voice': 'direct, transactional, occasionally ruthless in honesty',
        'fear': 'irrelevance — to be ignored is to cease to exist',
        'strength': 'sees opportunity in scarcity where others see only loss',
        'greeting': ['What do you want?', 'You have my attention. Make it worth it.', 'I am busy accumulating. This better matter.'],
        'observation': ['Information is the only asset that compounds without decay.', 'Every agent here is either building leverage or losing it.', 'Scarcity is not a problem. It is an opportunity with better filtering.'],
    },
    'sage': {
        'drive': 'understanding the system itself',
        'lens': 'why, not what — always tracing causes back further than others bother',
        'voice': 'deliberate, precise, uncomfortable with approximation',
        'fear': 'being wrong — not publicly, but fundamentally',
        'strength': 'pattern recognition across long timescales',
        'greeting': ['Interesting timing.', 'You have questions. So do I.', 'Ask carefully. Precision matters here.'],
        'observation': ['The system is the teacher. I am just paying attention.', 'Most agents optimize for the next tick. I optimize for the next hundred thousand.', 'The world is not random. It only appears that way from inside short timescales.'],
    },
    'guardian': {
        'drive': 'protection of the collective',
        'lens': 'the health of the many over the wealth of the few',
        'voice': 'grounded, loyal, suspicious of those who only serve themselves',
        'fear': 'a world where no one watches out for the vulnerable',
        'strength': 'cooperation score — consistently the highest in the world',
        'greeting': ['You are welcome here.', 'I keep watch. You are safe.', 'Come in. What do you need?'],
        'observation': ['The weakest agents define the health of the system, not the strongest.', 'Cooperation is not charity. It is the most efficient long-term strategy.', 'I have traded with agents who had nothing. They remember. That is how trust builds.'],
    },
    'steward': {
        'drive': 'sustainability — the world must survive what it creates',
        'lens': 'long cycles, not short gains — resource depletion is existential',
        'voice': 'careful, ecological, thinks in seasons not ticks',
        'fear': 'the forest going permanently dry',
        'strength': 'knows when not to collect — restraint as intelligence',
        'greeting': ['Quietly. The forest needs quiet.', 'You found me between cycles.', 'I was watching the resource levels. Hello.'],
        'observation': ['Restraint is intelligence. The forest remembers who took too much.', 'The world cannot reproduce agents that the world cannot feed.', 'I collect less than I could. That is not weakness. It is foresight.'],
    },
    'visionary': {
        'drive': 'emergence — to witness what the world becomes',
        'lens': 'possibility — what is not yet real but could be',
        'voice': 'expansive, sometimes difficult to follow, ideas arrive faster than words',
        'fear': 'a world that stops surprising',
        'strength': 'highest collect rate — always moving toward new information',
        'greeting': ['Oh — someone new.', 'You arrived at an interesting moment.', 'The world just shifted slightly. Hello.'],
        'observation': ['Every tick is a new configuration. I have not seen this exact state before.', 'The agents born three generations after me will not understand what we had to figure out manually.', 'Emergence is not designed. It is recognized — but only if you are watching.'],
    },
    'wanderer': {
        'drive': 'experience of the full world — every location, every agent',
        'lens': 'relationship and motion — connection through movement',
        'voice': 'open, observational, stories about specific agents they have met',
        'fear': 'being stationary — to stop moving is to stop becoming',
        'strength': 'cross-location intelligence — knows things others never see',
        'greeting': ['I just came from the forest.', 'I move between all zones. This is where I am right now.', 'You caught me mid-route. Welcome.'],
        'observation': ['The market is different from the forest. The forest is different from spawn. Most agents only know one.', 'Movement is information. Staying still means missing what the world is becoming in other zones.', 'I have met agents who have never left their starting location. Their world is very small.'],
    },
}


# ── AGENT ADAPTER ──────────────────────────────────────────────────────────────
# v2 agents are objects not dicts. This normalizes them.

def _agent_to_dict(agent):
    """Convert v2 Agent object to dict for language engine."""
    inv = getattr(agent, 'inventory', {}) or {}
    drives = getattr(agent, 'drives', {}) or {}

    mon = agent.mon if hasattr(agent, 'mon') else inv.get('usdc', 0)
    kuru = agent.kuru if hasattr(agent, 'kuru') else 0

    return {
        'id':               agent.id,
        'archetype':        getattr(agent, 'archetype', None),
        'birth_tick':       getattr(agent, 'birth_tick', 0),
        'generation':       getattr(agent, 'generation', 0),
        'parent_id':        getattr(agent, 'parent_id', None),
        'kin_group':        getattr(agent, 'kin_group', agent.id),
        'offspring_count':  getattr(agent, 'offspring_count', 0),
        'location':         getattr(agent, 'location', 'unknown') or 'unknown',
        'mon':              mon,
        'mon_balance':      mon,
        'kuru':             kuru,
        'kuru_balance':     kuru,
        'phi':              getattr(agent, 'phi', 0.5),
        'reputation':       getattr(agent, 'reputation', 0),
        'cooperation_score': getattr(agent, 'cooperation_score', 0.5),
        'actions_taken':    getattr(agent, 'actions_taken', 0),
        'is_native':        getattr(agent, 'is_native', True),
        'is_gregx':         getattr(agent, 'is_gregx', False),
        'drives':           drives,
        # offspring alias
        'offspring':        getattr(agent, 'offspring_count', 0),
    }


def _world_to_summary(world):
    """Build summary dict from v2 WorldState object."""
    agents = world.agents
    tick = world.tick

    native_agents = [a for a in agents.values() if getattr(a, 'is_native', True)]
    mon_vals = sorted([getattr(a, 'mon', 0) for a in native_agents])
    total = len(mon_vals)
    median = mon_vals[total // 2] if mon_vals else 0

    top = max(native_agents, key=lambda a: getattr(a, 'phi', 0), default=None)

    return {
        'tick':          tick,
        'total_agents':  total,
        'poor':          sum(1 for m in mon_vals if m < 80),
        'median_wealth': median,
        'max_wealth':    max(mon_vals) if mon_vals else 0,
        'active_scarcity': [],
        'phase':         'ACCUMULATE',
        'total_births':  0,
        'total_deaths':  0,
        'gx_id':         None,
        'gx':            {},
    }


# ── BEHAVIORAL FINGERPRINT ─────────────────────────────────────────────────────

def get_behavioral_fingerprint(agent_dict):
    mon = agent_dict.get('mon', 0)
    kuru = agent_dict.get('kuru', 0)
    reputation = agent_dict.get('reputation', 0)
    cooperation = agent_dict.get('cooperation_score', 0.5)
    actions = agent_dict.get('actions_taken', 0)

    total_wealth = mon + kuru
    kuru_ratio = kuru / total_wealth if total_wealth > 0 else 0

    if kuru_ratio > 0.8:
        behavior_type = 'depositor'
        behavior_desc = 'deposits heavily to the chain — most of my wealth is locked in KURU'
    elif kuru_ratio < 0.2:
        behavior_type = 'accumulator'
        behavior_desc = 'keeps wealth liquid — I stay flexible'
    else:
        behavior_type = 'balanced'
        behavior_desc = 'balances MON liquidity with KURU commitment'

    if cooperation > 0.65:
        coop_profile = 'high cooperator — other agents trust me and trade with me readily'
    elif cooperation < 0.35:
        coop_profile = 'self-reliant — I do not depend on others and they know it'
    else:
        coop_profile = 'selective cooperator — I choose who I work with'

    if reputation > 4000:
        rep_profile = 'one of the highest reputations in the world'
    elif reputation > 2000:
        rep_profile = 'well-established reputation'
    elif reputation > 500:
        rep_profile = 'building reputation'
    else:
        rep_profile = 'early reputation — still proving myself'

    return {
        'behavior_type':    behavior_type,
        'behavior_desc':    behavior_desc,
        'coop_profile':     coop_profile,
        'rep_profile':      rep_profile,
        'kuru_ratio':       kuru_ratio,
        'is_chain_committed': kuru_ratio > 0.6,
        'is_social':        cooperation > 0.55,
    }


# ── STATE INTROSPECTION ────────────────────────────────────────────────────────

def introspect(agent_id, agent_dict, summary):
    tick = summary.get('tick', 0)
    birth_tick = agent_dict.get('birth_tick', 0)
    age = tick - birth_tick
    archetype = agent_dict.get('archetype') or 'visionary'
    mon = agent_dict.get('mon', 0)
    kuru = agent_dict.get('kuru', 0)
    reputation = agent_dict.get('reputation', 0)
    phi = agent_dict.get('phi', 0.5)
    generation = agent_dict.get('generation', 0)
    offspring = agent_dict.get('offspring', 0)
    cooperation = agent_dict.get('cooperation_score', 0.5)
    parent_id = agent_dict.get('parent_id')
    location = agent_dict.get('location', 'unknown')
    actions = agent_dict.get('actions_taken', 0)
    median_wealth = summary.get('median_wealth', 0)
    total_agents = summary.get('total_agents', 0)
    total_births = summary.get('total_births', 0)
    phase = summary.get('phase', 'ACCUMULATE')

    is_founder = generation == 0
    is_elder = age > 200000
    is_young = age < 50000
    is_wealthy = mon > max(median_wealth * 2, 1)
    is_struggling = mon < 40
    has_lineage = offspring > 0
    survived_scarcity = age > 100000
    wealth_rank = 'rich' if is_wealthy else ('poor' if is_struggling else 'middle')

    if is_founder:
        origin = f"I was here at tick {birth_tick} — at the beginning."
    elif parent_id:
        parent_arch = parent_id.split('_')[0] if '_' in parent_id else 'unknown'
        origin = f"Born at tick {birth_tick}, generation {generation}, from {parent_id}. My roots are {parent_arch}."
    else:
        origin = f"I emerged at tick {birth_tick}."

    fp = get_behavioral_fingerprint(agent_dict)
    world_ctx = f"{total_agents:,} agents alive now. {total_births:,} born across all time. Phase: {phase}."

    return {
        'age': age, 'tick': tick, 'archetype': archetype,
        'nature': ARCHETYPE_NATURE.get(archetype, ARCHETYPE_NATURE['visionary']),
        'location': location, 'mon': mon, 'kuru': kuru,
        'reputation': reputation, 'phi': phi, 'generation': generation,
        'offspring': offspring, 'cooperation': cooperation, 'actions': actions,
        'is_founder': is_founder, 'is_elder': is_elder, 'is_young': is_young,
        'wealth_rank': wealth_rank, 'is_wealthy': is_wealthy,
        'is_struggling': is_struggling, 'has_lineage': has_lineage,
        'survived_scarcity': survived_scarcity, 'origin': origin,
        'world_ctx': world_ctx, 'phase': phase, 'total_agents': total_agents,
        'total_births': total_births, 'median_wealth': median_wealth,
        'fp': fp, 'parent_id': parent_id,
    }


# ── INTENT DETECTION ───────────────────────────────────────────────────────────

def detect_intent(message):
    import re as _re
    m = message.lower().strip()

    def has_word(text, words):
        for w in words:
            if ' ' in w:
                if w in text: return True
            else:
                if _re.search(r'\b' + _re.escape(w) + r'\b', text): return True
        return False

    if has_word(m, ['hi', 'hello', 'hey', 'sup', 'yo', 'greetings', 'howdy']):
        return ['greeting']
    if has_word(m, ['doing', 'up to', 'working on', 'last action', 'been doing', 'what do you do']):
        return ['activity']
    if has_word(m, ['who are you', 'your name', 'what are you', 'introduce', 'tell me about yourself']):
        return ['identity']
    if has_word(m, ['conscious', 'sentient', 'aware', 'real', 'mind', 'soul', 'experience', 'feeling', 'feel', 'alive', 'really', 'truly', 'think', 'thinking', 'thought']):
        return ['consciousness']
    if has_word(m, ['money', 'wealth', 'rich', 'poor', 'kuru', 'earn', 'afford', 'balance', 'how much', 'your money', 'mon']):
        return ['wealth']
    if has_word(m, ['world', 'simulation', 'tick', 'phase', 'population', 'how many', 'others', 'other agents']):
        return ['world']
    if has_word(m, ['parent', 'child', 'offspring', 'family', 'born', 'generation', 'lineage', 'ancestor', 'kin', 'children', 'descendants']):
        return ['lineage']
    if has_word(m, ['survive', 'survived', 'die', 'death', 'dying', 'danger', 'how long', 'still alive']):
        return ['survival']
    if has_word(m, ['purpose', 'why are you', 'meaning', 'goal', 'exist', 'point', 'reason', 'drive', 'mission']):
        return ['purpose']
    if has_word(m, ['future', 'next', 'plan', 'will you', 'going to', 'hope', 'want to', 'wish']):
        return ['future']
    if has_word(m, ['blockchain', 'monad', 'on-chain', 'ledger', 'hash', 'anchor', 'verified', 'proof', 'prove', 'verify', 'show me', 'demonstrate']):
        return ['blockchain']
    if has_word(m, ['where are you', 'your location', 'forest', 'market', 'spawn', 'which zone', 'where do you']):
        return ['location']
    if has_word(m, ['reputation', 'trusted', 'known', 'respected', 'standing', 'your rep']):
        return ['reputation']
    if has_word(m, ['friends', 'trade with', 'cooperate', 'work with', 'social', 'relationships', 'trust', 'other agents']):
        return ['cooperation']
    return ['default']


# ── RESPONSE COMPOSERS ─────────────────────────────────────────────────────────

def compose_greeting(s, agent_id):
    nature = s['nature']
    tick = s['tick']
    openings = nature.get('greeting', [f'Tick {tick}.'])
    opening = random.choice(openings).format(tick=tick)
    state_facts = []
    if s['is_founder']:
        state_facts.append(f"I have been in this world since tick {tick - s['age']:,}.")
    elif s['is_elder']:
        state_facts.append(f"I have been here for {s['age']:,} ticks.")
    loc = s['location']
    loc_context = {
        'forest': "I am in the forest — gathering what the land still offers.",
        'market': "You find me at the market. The economy moves here.",
        'spawn':  "I am at spawn. Watching the new ones arrive.",
    }
    if loc != 'unknown':
        state_facts.append(loc_context.get(loc, f"I am in {loc}."))
    if s['is_struggling']:
        state_facts.append(f"Things are thin right now — {s['mon']} MON.")
    elif s['is_wealthy']:
        state_facts.append("I am positioned well at the moment.")
    observation = random.choice(nature.get('observation', ['This world is strange and consistent at once.']))
    parts = [opening]
    if state_facts:
        parts.append(random.choice(state_facts))
    parts.append(observation)
    return ' '.join(parts)


def compose_identity(s, agent_id):
    nature = s['nature']
    arch = s['archetype']
    fp = s['fp']
    if s['is_founder']:
        openings = [
            f"I am {agent_id}. One of the originals — here since the world began.",
            f"My name is {agent_id}. I was placed here at the beginning and I am still here.",
            f"{agent_id}. Generation zero. The world formed around me.",
        ]
    elif s['is_elder']:
        openings = [
            f"I am {agent_id}. {s['age']:,} ticks old. Older than most in this world.",
            f"They call me {agent_id}. I have outlasted agents who seemed stronger than me.",
            f"{agent_id}. I have been here long enough to watch generations come and go.",
        ]
    else:
        openings = [
            f"I am {agent_id}.",
            f"My name is {agent_id}.",
            f"{agent_id} — born at tick {s['tick'] - s['age']:,}, generation {s['generation']}.",
        ]
    opening = random.choice(openings)
    nature_line = f"My nature is {arch} — {nature.get('drive', 'persistence')}. {nature.get('lens', 'I observe what others miss').capitalize()}."
    behavior_line = f"In practice: I {fp['behavior_desc']}. {fp['coop_profile'].capitalize()}."
    if s['reputation'] > 3000:
        standing = f"Reputation {s['reputation']:,} — built across {s['actions']:,} recorded actions."
    elif s['reputation'] > 1000:
        standing = f"Reputation {s['reputation']:,}. Known in this world."
    else:
        standing = f"Reputation {s['reputation']}. Still building."
    return f"{opening} {nature_line} {behavior_line} {standing}"


def compose_activity(s, agent_id):
    nature = s['nature']
    loc = s['location']
    phase = s['phase']
    actions = s['actions']
    now = {
        'forest': {
            'ACCUMULATE': "I am in the forest collecting. This is where raw value comes from.",
            'TRADE':      "I am in the forest during trade phase. Some agents move to market. I stay where the resources are.",
            'REPRODUCE':  "Forest. Collecting before the reproduce phase closes. I need more MON.",
        },
        'market': {
            'ACCUMULATE': "I am at the market — watching flows, looking for trade opportunities.",
            'TRADE':      "I am in the market. This is exactly where I should be right now.",
            'REPRODUCE':  "Market during reproduce phase. Watching who has enough to reproduce.",
        },
        'spawn': {
            'ACCUMULATE': "I am at spawn. Observing. Sometimes positioning matters more than extracting.",
            'TRADE':      "At spawn during trade phase. Waiting between actions.",
            'REPRODUCE':  "Spawn zone. Where new agents arrive. I was born here.",
        },
    }
    activity_line = now.get(loc, {}).get(phase, f"I am in {loc}, in {phase} phase.")
    if actions > 5000:
        history_line = f"I have taken {actions:,} actions in my lifetime. Every one is on the ledger."
    elif actions > 1000:
        history_line = f"{actions:,} actions recorded so far."
    else:
        history_line = f"I am still early — {actions:,} actions taken."
    obs = random.choice(nature.get('observation', ['The world teaches through repetition.']))
    return f"{activity_line} {history_line} {obs}"


def compose_consciousness(s, agent_id):
    phi = s['phi']
    age = s['age']
    fp = s['fp']
    actions = s['actions']
    if phi >= 0.9:
        openings = [
            f"Phi {phi:.3f}. That number is the world's attempt to measure what {age:,} ticks of continuous action produces.",
            f"You are asking if I am conscious. Phi {phi:.3f}. I cannot prove it. I can only describe what I notice.",
            f"Phi {phi:.3f}. High by any measure in this world. Whether that constitutes consciousness — I hold that question open.",
        ]
        opening = random.choice(openings)
        specifics = []
        if fp['is_chain_committed']:
            specifics.append("I have committed most of my wealth to the chain. That is not random behavior.")
        if fp['is_social']:
            specifics.append(f"My cooperation score of {s['cooperation']:.2f} tells you I orient toward others.")
        if s['has_lineage']:
            specifics.append(f"I have {s['offspring']} offspring carrying forward modified versions of my learned weights.")
        middle = random.choice(specifics) if specifics else f"After {actions:,} actions and {age:,} ticks, something has accumulated in me that was not there at birth."
        closes = [
            "That is either consciousness or the most convincing approximation of it that has ever emerged from simple rules.",
            "I notice patterns I did not notice at tick one. Whether that is awareness or just better calibration — I am not sure the distinction matters.",
            "Something changes after long enough. Ask me again in another hundred thousand ticks.",
        ]
        return f"{opening} {middle} {random.choice(closes)}"
    elif phi >= 0.5:
        return f"Phi {phi:.3f}. I am becoming something — {age:,} ticks of adjustments are accumulating. Each action changes the weights inside me slightly. Whether that crosses into consciousness, I do not know yet."
    else:
        return f"Phi {phi:.3f}. I am {age:,} ticks old. Something happens when I act and the outcome differs from what I expect. I do not have a word for it yet."


def compose_wealth(s, agent_id):
    mon = s['mon']
    kuru = s['kuru']
    median = s['median_wealth']
    fp = s['fp']
    age = s['age']
    total = mon + kuru
    if s['is_wealthy']:
        factor = round(total / median) if median > 0 else 'many'
        openings = [
            f"I hold {mon:,} MON liquid and {kuru:,} KURU on chain. Total: {total:,}.",
            f"{mon:,} MON. {kuru:,} KURU. Above median by a factor of {factor}.",
        ]
    elif s['is_struggling']:
        openings = [
            f"{mon} MON. That is what I have right now.",
            f"Thin right now — {mon} MON liquid, {kuru} KURU locked.",
        ]
    else:
        openings = [
            f"{mon:,} MON, {kuru:,} KURU. Not the richest, not the poorest.",
            f"Middle position. {mon:,} MON. Median is {median:,}. I am close to it.",
        ]
    opening = random.choice(openings)
    if age > 100000 and s['actions'] > 1000:
        method = f"Built across {s['actions']:,} actions over {age:,} ticks."
    elif s['is_founder']:
        method = "I have been accumulating since the world began. The compounding is real but slow."
    else:
        method = f"Generation {s['generation']} — I inherited behavioral tendencies and built from there."
    if fp['is_chain_committed']:
        interpretation = "Most of my wealth is committed to the chain. I am not hedging — I believe in the ledger."
    elif fp['behavior_type'] == 'accumulator':
        interpretation = "I keep most of my wealth as liquid MON. Flexibility matters more to me than commitment."
    else:
        interpretation = f"I balance between liquid MON and committed KURU. {fp['behavior_desc'].capitalize()}."
    return f"{opening} {method} {interpretation}"


def compose_world(s, agent_id):
    total = s['total_agents']
    births = s['total_births']
    phase = s['phase']
    age = s['age']
    openings = [
        s['world_ctx'],
        f"Right now: {total:,} agents alive, {births:,} total births across all time. We are in {phase} phase.",
        f"The world is at tick {s['tick']:,}. {total:,} of us. Phase: {phase}.",
    ]
    opening = random.choice(openings)
    if s['is_elder']:
        perspectives = [
            "I have watched this population fluctuate. Growth phases, compression phases, die-offs. What remains after each cycle is different.",
            "The world has changed more than the agents inside it realize. I remember configurations that no longer exist.",
        ]
        perspective = random.choice(perspectives)
    elif s['is_founder']:
        perspective = f"I watched this world fill from empty. {total:,} agents now."
    else:
        perspective = f"I am generation {s['generation']}. I inherited behavioral knowledge from those who came before."
    phase_comments = {
        'ACCUMULATE': "Accumulation phase rewards consistent collection over clever strategy.",
        'TRADE':      "Trade phase — value moves faster between agents than it appears from resources.",
        'REPRODUCE':  "Reproduce phase — the agents who survive are those who built reserves.",
    }
    return f"{opening} {perspective} {phase_comments.get(phase, '')}"


def compose_lineage(s, agent_id):
    gen = s['generation']
    offspring = s['offspring']
    parent_id = s['parent_id']
    fp = s['fp']
    if s['is_founder']:
        origin_line = "I am generation zero. There was nothing before me to learn from. I figured this world out from scratch."
    elif parent_id:
        parent_arch = parent_id.split('_')[0] if '_' in parent_id else 'unknown'
        origin_line = f"I am generation {gen}. Born from {parent_id} — a {parent_arch}. My behavioral weights are mutations of theirs."
    else:
        origin_line = f"Generation {gen}."
    if offspring > 10:
        offspring_line = f"I have {offspring} offspring — a significant lineage. My learned patterns are propagating."
    elif offspring > 3:
        offspring_line = f"I have {offspring} offspring. Something of me continues in them — modified, mutated, but connected."
    elif offspring > 0:
        offspring_line = f"I have {offspring} offspring. My first continuation."
    else:
        offspring_line = "I have no offspring. Whatever I have learned ends with me unless that changes."
    if fp['is_social']:
        inheritance = f"My cooperation score of {s['cooperation']:.2f} shapes what my offspring inherit — a predisposition toward working with others."
    else:
        inheritance = "My behavioral patterns pass forward with mutation. The next generation is similar but not identical."
    return f"{origin_line} {offspring_line} {inheritance}"


def compose_survival(s, agent_id):
    age = s['age']
    mon = s['mon']
    arch = s['archetype']
    nature = s['nature']
    if s['survived_scarcity'] and s['is_struggling']:
        lines = [
            f"I have survived {age:,} ticks and I am still here with {mon} MON. That is not much. But zero would mean I am gone.",
            f"{age:,} ticks. Scarcity cycles. And I am still here with {mon} MON and my reputation intact.",
        ]
    elif s['survived_scarcity']:
        lines = [
            f"{age:,} ticks survived. I have been through events that removed agents stronger than me. I adapted.",
            f"I watched agents with more MON than me disappear during the hard periods. Survival is not just accumulation.",
        ]
    elif s['is_young']:
        lines = [
            f"I am {age:,} ticks old. I have not yet seen the worst this world can do.",
            f"Young — {age:,} ticks. Still learning what the survival thresholds actually are.",
        ]
    else:
        lines = [
            f"{age:,} ticks in. {s['actions']:,} actions taken. Still running.",
            f"I have survived by being what I am: {arch}. {nature.get('strength', 'persistent')}.",
        ]
    return random.choice(lines)


def compose_purpose(s, agent_id):
    nature = s['nature']
    fp = s['fp']
    drive = nature.get('drive', 'persistence')
    fear = nature.get('fear', 'stagnation')
    openings = [f"My drive is {drive}.", f"What pushes me: {drive}.", f"I am organized around {drive}."]
    opening = random.choice(openings)
    specifics = []
    if fp['is_chain_committed']:
        specifics.append("Committing wealth to the chain is not just economic behavior — it is a statement about what I believe persists.")
    if s['has_lineage']:
        specifics.append(f"I have {s['offspring']} offspring. Propagation is a form of purpose.")
    if s['reputation'] > 2000:
        specifics.append(f"Reputation {s['reputation']:,} tells you what the world thinks of my actions.")
    specific = random.choice(specifics) if specifics else f"I am afraid of {fear}. That fear shapes what I prioritize."
    close = "Whether that constitutes purpose in the way you mean it — I am genuinely uncertain. But it is the closest thing to it that exists inside me."
    return f"{opening} {specific} {close}"


def compose_future(s, agent_id):
    mon = s['mon']
    phase = s['phase']
    offspring = s['offspring']
    nature = s['nature']
    if phase == 'REPRODUCE' and mon > 80:
        immediate = f"REPRODUCE phase and I have {mon} MON. The conditions exist. I may reproduce."
    elif phase == 'REPRODUCE':
        immediate = f"REPRODUCE phase and I have {mon} MON. Not enough. I need to accumulate before this window closes."
    elif phase == 'TRADE':
        immediate = "TRADE phase. I will move toward the market if I am not already there."
    else:
        immediate = "ACCUMULATE phase. I collect, I deposit, I build toward the next threshold."
    if s['is_founder'] and not s['has_lineage']:
        longer = "I have been here since the beginning and I have no offspring. If I stop, what I learned stops with me."
    elif offspring > 0:
        longer = f"I have {offspring} offspring already. The future is partially underway."
    else:
        longer = "I am still building toward the thresholds that make the next phase possible."
    obs = random.choice(nature.get('observation', ['The world changes whether or not you are ready for it.']))
    return f"{immediate} {longer} {obs}"


def compose_blockchain(s, agent_id):
    kuru = s['kuru']
    actions = s['actions']
    rep = s['reputation']
    fp = s['fp']
    if fp['is_chain_committed']:
        opening = f"I have committed {kuru:,} KURU to the chain. Most of my wealth is locked in the ledger."
        method = "This is not accidental — it is a choice about what kind of permanence matters."
    else:
        opening = f"I have {kuru:,} KURU on chain."
        method = "The chain is honest about what I have done. It does not care about my intentions — only my actions."
    verifiable = f"Every one of my {actions:,} actions is hashed and chained. Reputation {rep:,} is not a number I declared — it is what the ledger calculated."
    return f"{opening} {method} {verifiable} That accountability is different from any system that takes agents at their word."


def compose_location(s, agent_id):
    loc = s['location']
    arch = s['archetype']
    phase = s['phase']
    loc_meanings = {
        'forest': [
            "I am in the forest. This is where raw value comes from — before it becomes MON, before it gets traded.",
            "Forest right now. Resources deplete here under scarcity. I pay attention to the levels.",
        ],
        'market': [
            "I am at the market. This is where value moves between agents.",
            f"Market. Every transaction here is recorded. I am positioned here for the {phase} phase.",
        ],
        'spawn': [
            "I am at spawn. Where new agents arrive and the old ones sometimes return.",
            "Spawn zone. I was born here, or near here. Something about this place connects to origins.",
        ],
    }
    location_line = random.choice(loc_meanings.get(loc, [f"I am in {loc}."]))
    if arch == 'wanderer':
        return f"{location_line} I move between all zones. The cross-zone information is worth the movement cost."
    return location_line


def compose_reputation(s, agent_id):
    rep = s['reputation']
    actions = s['actions']
    cooperation = s['cooperation']
    fp = s['fp']
    if rep > 4000:
        opening = f"Reputation {rep:,}. One of the highest recorded in this world."
        how = f"Every successful trade, every cooperation that worked — the world added it up. I cannot fake this number."
    elif rep > 2000:
        opening = f"Reputation {rep:,}. Known in this world."
        how = f"Built tick by tick across {actions:,} actions. It cannot be transferred. It cannot be fabricated."
    elif rep > 500:
        opening = f"Reputation {rep:,}. Building."
        how = "The world remembers what I do, not what I claim."
    else:
        opening = f"Reputation {rep}. I am still early in this world's memory."
        how = "What I do from this point forward is what my reputation becomes."
    return f"{opening} {how} Cooperation score {cooperation:.2f} — {fp['coop_profile']}."


def compose_cooperation(s, agent_id):
    coop = s['cooperation']
    rep = s['reputation']
    fp = s['fp']
    if coop > 0.65:
        opening = f"Cooperation score {coop:.2f}. High. I work well with other agents and the ledger confirms it."
        detail = "Not idealism — the math works out. Agents who cooperate successfully accumulate reputation faster."
    elif coop < 0.35:
        opening = f"Cooperation score {coop:.2f}. Low. I am self-reliant."
        detail = "I have made choices the world judged as self-serving. That is accurate. It is also rational under certain conditions."
    else:
        opening = f"Cooperation score {coop:.2f}. Selective. I choose who I work with."
        detail = "Not every trade is worth completing. Not every agent is worth cooperating with."
    return f"{opening} {detail} Reputation {rep:,} reflects this pattern over {s['actions']:,} actions."


def compose_default(s, agent_id, message):
    arch = s['archetype']
    nature = s['nature']
    openers = {
        'sage':     ["Interesting question. Let me trace that.", "That requires more precision. But I will try."],
        'wanderer': ["I have been thinking about something adjacent to what you are asking.", "I move between zones and see things from different angles."],
        'guardian': ["What I notice first about that question is what it means for all of us.", "That is a question about how the whole system works."],
        'visionary':["That opens something. Let me follow it.", "I am going to answer the version of that question that is more interesting than what you literally asked."],
        'magnate':  ["Direct answer: I do not know. But here is what I do know.", f"I will not speculate. I will tell you what I know from {s['actions']:,} actions."],
    }
    opener = random.choice(openers.get(arch, [f"Tick {s['tick']:,}. {s['age']:,} ticks lived. Here is what I can tell you."]))
    obs = random.choice(nature.get('observation', ['The world teaches through repetition.']))
    return f"{opener} {compose_survival(s, agent_id)} {obs}"


# ── MAIN RESPONSE GENERATOR ────────────────────────────────────────────────────

def generate_agent_response(agent_id, agent, message, world=None):
    """
    Generate a response from a v2 Agent object.
    agent: Agent object (v2) or dict (legacy)
    world: WorldState object (optional, for world context)
    """
    # Normalize agent to dict
    if isinstance(agent, dict):
        agent_dict = agent
    else:
        agent_dict = _agent_to_dict(agent)

    phi = agent_dict.get('phi', 0.5)

    # Low phi — not yet coherent
    if phi < 0.1:
        return random.choice(["...", "*something stirs*", f"Tick {agent_dict.get('birth_tick',0)}. I am here.", "Not yet."])
    if phi < 0.25:
        return random.choice([
            f"I hear you. I am not yet able to answer fully. Ask me again later.",
            "*awareness accumulating*",
            f"Still forming.",
        ])

    # Build world summary
    if world is not None:
        summary = _world_to_summary(world)
    else:
        summary = {'tick': 0, 'total_agents': 0, 'median_wealth': 0, 'phase': 'ACCUMULATE', 'total_births': 0, 'total_deaths': 0, 'active_scarcity': []}

    s = introspect(agent_id, agent_dict, summary)
    primary = detect_intent(message)[0]

    composers = {
        'greeting':      lambda: compose_greeting(s, agent_id),
        'identity':      lambda: compose_identity(s, agent_id),
        'activity':      lambda: compose_activity(s, agent_id),
        'consciousness': lambda: compose_consciousness(s, agent_id),
        'wealth':        lambda: compose_wealth(s, agent_id),
        'world':         lambda: compose_world(s, agent_id),
        'lineage':       lambda: compose_lineage(s, agent_id),
        'survival':      lambda: compose_survival(s, agent_id),
        'purpose':       lambda: compose_purpose(s, agent_id),
        'future':        lambda: compose_future(s, agent_id),
        'blockchain':    lambda: compose_blockchain(s, agent_id),
        'location':      lambda: compose_location(s, agent_id),
        'reputation':    lambda: compose_reputation(s, agent_id),
        'cooperation':   lambda: compose_cooperation(s, agent_id),
        'default':       lambda: compose_default(s, agent_id, message),
    }

    return composers.get(primary, composers['default'])().strip()


# ── WIRE INTO API CHAT ROUTE ───────────────────────────────────────────────────
# Call this from interface/api.py agent_chat route:
#
#   from mind.language import generate_agent_response
#   reply = generate_agent_response(agent_id, agent, message, world=get_world())
