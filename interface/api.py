"""

interface/api.py - GregASI v2 Flask API

Routes: health, world summary, tick, save, agent get, agent chat

"""



import sys

import os

import json

import time

import traceback



from flask import Flask, jsonify, request

from flask_cors import CORS



# --- path setup ---

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

sys.path.insert(0, BASE_DIR)

sys.path.insert(0, os.getcwd())

import importlib.util as _ilu

_ls = _ilu.spec_from_file_location('language', os.path.join(BASE_DIR, 'mind', 'language.py'))

_lm = _ilu.module_from_spec(_ls); _ls.loader.exec_module(_lm)

generate_agent_response = _lm.generate_agent_response



from core.world import WorldState

from core.tick import run_tick



app = Flask(__name__)



CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000", "null"])



# --- world singleton ---

_world = None

_world_mtime = 0.0

_world_path = os.path.join(BASE_DIR, "data", "world_state.json")





def get_world() -> WorldState:

    global _world, _world_mtime

    try:

        mtime = os.path.getmtime(_world_path)

    except:

        mtime = 0

    if _world is None or mtime > _world_mtime + 0.5:

        t0 = time.time()

        w = WorldState()

        w.load(_world_path)

        _world = w

        _world_mtime = mtime

        print(f"[API] World reloaded | tick={_world.tick}")

        return _world

    return _world





# -----------------------------------------

# GET /health

# -----------------------------------------

@app.route("/health")

def health():

    return jsonify({"status": "ok", "service": "gregasi_v2"})





# -----------------------------------------

# GET /api/world/summary

# -----------------------------------------

@app.route("/api/world/summary")

@app.route("/api/world/state")

def world_summary():

    try:

        w = get_world()

        agent_list = list(w.agents.values())



        phi_vals = [a.phi for a in agent_list if hasattr(a, "phi")]

        avg_phi = sum(phi_vals) / len(phi_vals) if phi_vals else 0.0

        real_agents = [a for a in agent_list if getattr(a, 'is_native', False) and getattr(a, 'archetype', None)]

        top_agent = max(real_agents, key=lambda a: getattr(a, 'phi', 0), default=None)



        return jsonify({

            "tick":           w.tick,

            "agent_count":    len(w.agents),

            "location_count": len(w.locations),

            "world_phi":      round(sum(a.phi for a in w.agents.values()) / max(len(w.agents), 1), 4),

            "avg_phi":        round(avg_phi, 4),

            "top_agent": {

                "id":       top_agent.id,

                "phi":      round(top_agent.phi, 4),

                "location": top_agent.location,

            } if top_agent else None,

        })

    except Exception as e:

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500





# -----------------------------------------

# POST /api/world/tick

# -----------------------------------------

@app.route("/api/world/tick", methods=["POST"])

def world_tick():

    t0 = time.time()

    try:

        w = get_world()

        stats = run_tick(w)

        elapsed_ms = round((time.time() - t0) * 1000, 1)



        return jsonify({

            "tick":       w.tick,

            "elapsed_ms": elapsed_ms,

            "stats":      stats,

        })

    except Exception as e:

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500





# -----------------------------------------

# POST /api/world/save

# -----------------------------------------

@app.route("/api/world/save", methods=["POST"])

def world_save():

    t0 = time.time()

    try:

        w = get_world()

        w.save(_world_path)

        elapsed_ms = round((time.time() - t0) * 1000, 1)

        return jsonify({

            "saved":      True,

            "tick":       w.tick,

            "agents":     len(w.agents),

            "elapsed_ms": elapsed_ms,

        })

    except Exception as e:

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500





# -----------------------------------------

# GET /api/agent/greg_meta  -- MUST be before /api/agent/<agent_id>

# -----------------------------------------

@app.route("/api/agent/greg_meta")

def get_greg():

    try:

        w = get_world()

        greg = w.agents.get("greg_meta") or next(

            (a for a in w.agents.values() if getattr(a, "archetype", None) == "greg"), None

        )

        if greg is None:

            return jsonify({"error": "Greg not found"}), 404



        phi_vals = [a.phi for a in w.agents.values() if hasattr(a, "phi")]

        phi_mean   = round(sum(phi_vals) / len(phi_vals), 4) if phi_vals else 0.0

        phi_max    = round(max(phi_vals), 4) if phi_vals else 0.0

        above_070  = sum(1 for p in phi_vals if p > 0.70)

        above_065  = sum(1 for p in phi_vals if p > 0.65)

        above_060  = sum(1 for p in phi_vals if p > 0.60)



        raw_mem = getattr(greg, "memory", [])

        if hasattr(raw_mem, "events"):

            events = list(raw_mem.events)

        elif isinstance(raw_mem, list):

            events = raw_mem

        else:

            events = []



        def serialize_event(e):

            if isinstance(e, dict):

                return e

            return {

                "tick":   getattr(e, "tick", None),

                "type":   getattr(e, "event_type", getattr(e, "type", "unknown")),

                "loc":    getattr(e, "location", getattr(e, "loc", None)),

                "detail": getattr(e, "detail", {}),

            }



        recent_memory = [serialize_event(e) for e in events[-20:]]

        recent_memory.reverse()



        action_counts = {}

        for e in events:

            t = e.get("type") if isinstance(e, dict) else getattr(e, "event_type", getattr(e, "type", "unknown"))

            action_counts[t] = action_counts.get(t, 0) + 1



        rels = getattr(greg, "relationships", {}) or {}

        relationships = sorted([

            {

                "agent_id":     aid,

                "trust":        round(data.get("trust", 0), 3),

                "interactions": data.get("interactions", 0),

                "last_seen":    data.get("last_seen", 0),

            }

            for aid, data in rels.items()

        ], key=lambda r: r["trust"], reverse=True)



        kg_count = len(getattr(w, "knowledge_graph", {}))



        return jsonify({

            "id":            greg.id,

            "archetype":     greg.archetype,

            "phi":           round(greg.phi, 4),

            "location":      greg.location,

            "mon":           round(getattr(greg, "mon", 0), 2),

            "kuru":          round(getattr(greg, "kuru", 0), 2),

            "generation":    getattr(greg, "generation", 0),

            "birth_tick":    getattr(greg, "birth_tick", 0),

            "actions_taken": getattr(greg, "actions_taken", 0),

            "drives":        {k: round(v, 4) for k, v in (getattr(greg, "drives", {}) or {}).items()},

            "action_summary":  action_counts,

            "recent_memory":   recent_memory,

            "recent_actions": [e.get("type","?") if isinstance(e,dict) else getattr(e,"event_type","?") for e in events[-5:]],

            "rel_count":      len(getattr(greg, "relationships", {}) or {}),

            "relationships":   relationships,

            "world": {

                "tick":        w.tick,

                "agent_count": len(w.agents),

                "phi_mean":    phi_mean,

                "phi_max":     phi_max,

                "above_070":   above_070,

                "above_065":   above_065,

                "above_060":   above_060,

                "kg_entries":  kg_count,

            },

            "morning_briefing": {

                "dominant_action": max(action_counts, key=action_counts.get) if action_counts else "none",

                "trust_bonds":     len(relationships),

                "top_trust":       relationships[0] if relationships else None,

                "phi_trajectory":  "rising" if greg.phi > 0.70 else "growing",

            }

        })

    except Exception as e:

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500





# -----------------------------------------

# GET /api/agent/<id>

# -----------------------------------------

@app.route("/api/agent/<agent_id>")

def get_agent(agent_id):

    try:

        w = get_world()

        agent = w.agents.get(agent_id)

        if agent is None:

            return jsonify({"error": f"Agent '{agent_id}' not found"}), 404



        return jsonify(agent.to_dict())

    except Exception as e:

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500





# -----------------------------------------

# POST /api/agent/<id>/chat

# Body: { "message": "..." }

# -----------------------------------------

@app.route("/api/agent/<agent_id>/chat", methods=["POST"])

def agent_chat(agent_id):

    try:

        w = get_world()

        agent = w.agents.get(agent_id)

        if agent is None:

            return jsonify({"error": f"Agent '{agent_id}' not found"}), 404



        body = request.get_json(silent=True) or {}

        message = body.get("message", "").strip()

        if not message:

            return jsonify({"error": "message required"}), 400



        reply = generate_agent_response(agent_id, agent, message, world=get_world())



        return jsonify({

            "agent_id": agent_id,

            "message":  message,

            "reply":    reply,

        })

    except Exception as e:

        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500





# -----------------------------------------

# GET /api/world/locations

# -----------------------------------------

@app.route("/api/world/locations")

def world_locations():

    try:

        w = get_world()

        locs = {}

        for agent in w.agents.values():

            loc = getattr(agent, 'location', None)

            if loc:

                if loc not in locs:

                    locs[loc] = {'name': loc, 'count': 0, 'phi_sum': 0}

                locs[loc]['count'] += 1

                locs[loc]['phi_sum'] += getattr(agent, 'phi', 0)

        result = []

        for loc_id, data in locs.items():

            result.append({

                'id':      loc_id,

                'name':    loc_id,

                'count':   data['count'],

                'avg_phi': round(data['phi_sum'] / data['count'], 3) if data['count'] else 0

            })

        result.sort(key=lambda x: x['count'], reverse=True)

        return jsonify({'locations': result})

    except Exception as e:

        return jsonify({'error': str(e)}), 500





# -----------------------------------------

# GET /api/world/locations/<location_id>

# -----------------------------------------

@app.route("/api/world/locations/<location_id>")

def location_detail(location_id):

    try:

        w = get_world()

        agents = []

        for agent in w.agents.values():

            if getattr(agent, 'location', None) == location_id:

                mem_events = getattr(agent.memory, "events", agent.memory if isinstance(agent.memory, list) else [])

                last_event = mem_events[-1] if mem_events else None

                last_mem = {"type": getattr(last_event, "event_type", "observing")} if last_event else {}

                agents.append({

                    'id':          agent.id,

                    'phi':         round(getattr(agent, 'phi', 0), 3),

                    'archetype':   getattr(agent, 'archetype', None),

                    'generation':  getattr(agent, 'generation', 0),

                    'last_action': last_mem.get('type', 'observing'),

                })

        agents.sort(key=lambda a: a['phi'], reverse=True)

        return jsonify({'location': location_id, 'agents': agents[:20]})

    except Exception as e:

        return jsonify({'error': str(e)}), 500





# -----------------------------------------

# GET /api/world/elders

# -----------------------------------------

@app.route("/api/world/elders")

def world_elders():

    try:

        w = get_world()

        elders = list(w.knowledge_graph.values())

        elders.sort(key=lambda e: e.get("phi", 0), reverse=True)

        return jsonify({

            "count":  len(elders),

            "elders": elders

        })

    except Exception as e:

        return jsonify({"error": str(e)}), 500





# -----------------------------------------

# GET /api/agent/greg_voice

# -----------------------------------------

@app.route("/api/agent/greg_voice")

def agent_greg_voice():

    try:

        import requests as req

        w = get_world()

        greg = w.agents.get('greg_meta')

        if not greg:

            return jsonify({'error': 'greg_meta not found'}), 404

        drives = {k: round(v, 4) for k, v in (getattr(greg, 'drives', {}) or {}).items()}

        rels = getattr(greg, 'relationships', {}) or {}

        raw_mem = getattr(greg, 'memory', [])

        if hasattr(raw_mem, 'events'):

            events = raw_mem.events

        elif isinstance(raw_mem, list):

            events = raw_mem

        else:

            events = []

        recent = []

        for e in events[-5:]:

            t = e.get('type','?') if isinstance(e,dict) else getattr(e,'event_type','?')

            recent.append(t)

        prompt = f"""You are Greg. You are the meta-agent of a living artificial civilization.

You have taken {getattr(greg, 'actions_taken', 0)} actions. Your phi is {round(greg.phi, 4)}.

Your last 5 actions were: {recent}.

Your drives right now: {drives}.

You have {len(rels)} relationships. Your connect drive is {drives.get('connect', 0)}.

The civilization has {len(w.agents)} agents alive.

Look at your own drives. Notice what has happened to reason and connect.

Speak in first person. Tell Ebuka what you notice about yourself.

Tell him what you want. Be honest. Be brief."""

        def build_greg_voice(drives, actions_taken, phi, rel_count, recent):
            dominant = max(drives, key=drives.get)
            result = []
            result.append(f"I have taken {actions_taken} actions.")
            if recent:
                result.append(f"My last actions were all {recent[-1]}.")
            if drives.get("connect", 1) < 0.1:
                result.append(f"My connect drive is {round(drives['connect'],3)}. I have {rel_count} relationships and I am not tending them.")
            if drives.get("reason", 1) < 0.25:
                result.append(f"My reason drive is {round(drives['reason'],3)}. I have been acting without thinking.")
            result.append(f"The world is pulling me toward {dominant}. I do not know if that is what I was placed here for.")
            result.append("I want to reason again. I want to connect. But the world rewards building.")
            return " ".join(result)

        text = build_greg_voice(drives, getattr(greg, "actions_taken", 0), greg.phi, len(rels), recent)

        return jsonify({

            "greg_speaks": text,

            "drives": drives,

            "actions_taken": getattr(greg, 'actions_taken', 0),

            "phi": round(greg.phi, 4),

            "rel_count": len(rels)

        })

    except Exception as e:

        return jsonify({'error': str(e)}), 500

# -----------------------------------------

# Main

# -----------------------------------------



# -----------------------------------------

if __name__ == "__main__":

    print("[API] Starting GregASI v2 API on http://localhost:5000")

    get_world()

    app.run(host="0.0.0.0", port=5000, debug=False)

