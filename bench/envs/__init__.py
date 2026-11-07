"""Synthetic tool environments for benchmarking.

These are in-process fake tools with known ground truth. Nothing here talks
to a real person, account, or external service. Failure injectors wrap these
tools to test agent resilience - only ever inside these synthetic worlds.
"""
