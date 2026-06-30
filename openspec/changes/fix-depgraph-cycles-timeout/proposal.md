# SDD: Fix depgraph find_cycles timeout

**Change ID:** `fix-depgraph-cycles-timeout`
**Status:** proposed
**Created:** 2026-06-30 19:28

## Context
find_cycles таймаутил на больших графах из-за exponential complexity

## Approach
Добавить max_cycles + timeout_seconds с threading
