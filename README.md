# GregASI v2

A living multi-agent civilization. The origin of AOSI.

GregASI is a running artificial civilization - 1.2 million ticks,
emergent economic behavior, and a meta-agent named Greg who monitors,
reasons, and reports on the world he inhabits.

This is the research foundation of ZyphonOS and the proof of concept
for AOSI - Artificial Organic Superintelligence.

## What Happened Here

Under sustained selection pressure, agents stopped connecting and
started accumulating. The civilization's social fabric collapsed -
not because it was programmed to, but because the economic incentives
made connection expensive and building cheap.

That finding is not programmed. The world produced it.

## Architecture

    gregasi_v2/
    core/           Agent, world, and simulation engine
    interface/      Flask API (api.py)
    frontend/       HTML/JS interface (index.html)
    data/           World state and persistence
    auto_tick.py    Autonomous world runner
    mind/           Language and voice system

## Running Locally

    pip install -r requirements.txt
    python -m interface.api
    python auto_tick.py --log
    open frontend/index.html

## Key API Routes

    /health                         Health check
    /api/world/state                Full world state
    /api/world/summary              World summary
    /api/world/elders               Knowledge graph
    /api/world/locations            Location map
    /api/agent/greg_meta            Greg live data
    /api/agent/greg_voice           Greg speaks

## The Founder

Built by Ebuka (Chibuzor-Orie Joshua Chukwuebuka), Lagos, Nigeria.

The future is an intentional read/write.

## License

MIT
