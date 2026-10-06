"""
Step 5 Orchestrator: Target Code Synthesis Runner (Alias).
===========================================================
Re-exports TargetSynthesisRunner and run_conformance_gate from target_synthesis_runner.
"""

from pipeline_core.workflows.target_synthesis_runner import (
    TargetSynthesisRunner,
    main,
    run_conformance_gate,
    run_target_synthesis,
)

__all__ = [
    "TargetSynthesisRunner",
    "run_conformance_gate",
    "run_target_synthesis",
    "main",
]
