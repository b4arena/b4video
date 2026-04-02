---
title: "Beads: Task Tracking for AI Agents"
voice: b4arena-default
avatar: presenter-01
resolution: 1920x1080
fps: 30
---

## Intro
<!-- type: presenter -->
Welcome to b4arena. Today we'll look at Beads, our Dolt-powered issue
tracker designed for multi-session agentic workflows. Beads lets AI agents
create, track, and close tasks with full dependency management and
persistent memory across conversation compaction.

## Creating Tasks
<!-- type: demo -->
<!-- showboat: demos/beads-create.sh -->
Here we create a new task with dependencies. Notice how beads automatically
tracks the blocking relationship between the implementation task and the
testing task. The bd ready command shows only tasks with no blockers,
so agents always know what to work on next.

## Dependency Management
<!-- type: demo -->
<!-- showboat: demos/beads-deps.sh -->
When we close the implementation task, the testing task automatically
becomes unblocked. The bd close command with the suggest-next flag
shows which tasks are newly available. This is how agents hand off
work to each other without explicit coordination.

## Architecture
<!-- type: presenter -->
Under the hood, beads uses Dolt — a version-controlled database that
speaks SQL. Every agent session commits to the same branch, giving us
full history and conflict resolution. You can push and pull beads
between machines, just like git.

## Outro
<!-- type: presenter -->
That's beads in action — persistent task tracking that survives
conversation compaction and works across multiple agents. Check out
the b4arena GitHub org for the source code, and subscribe for more
deep dives into our agentic infrastructure.
