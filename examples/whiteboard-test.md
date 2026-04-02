---
title: "How #B4arena Agents Coordinate"
voice: b4arena-default
avatar: presenter-01
resolution: 1920x1080
fps: 30
---

## Intro
<!-- type: presenter -->
Let me show you how our agents coordinate in B4arena.

## Agent Flow
<!-- type: whiteboard -->
<!-- diagram: diagrams/agent-coordination.yaml -->
Forge writes the code and opens a pull request. Atlas reviews it through the Four Eyes Protocol, ensuring no single agent can merge alone. Rio validates the design decisions. All three agents track their work through Beads, our Dolt-powered issue tracker that persists across sessions.

## Outro
<!-- type: presenter -->
That's agent coordination in B4arena. Three agents, one shared tracker, zero humans in the loop.
