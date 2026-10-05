from .modernization_workflow import ModernizationWorkflowEngine

def __getattr__(name: str):
    if name in ("CognitiveExtractionRunner", "run_cognitive_chain"):
        from .cognitive_runner import CognitiveExtractionRunner, run_cognitive_chain
        mapping = {
            "CognitiveExtractionRunner": CognitiveExtractionRunner,
            "run_cognitive_chain": run_cognitive_chain,
        }
        return mapping[name]
    if name in ("TargetSynthesisRunner", "run_target_synthesis"):
        from .target_synthesis_runner import TargetSynthesisRunner, run_target_synthesis
        mapping = {
            "TargetSynthesisRunner": TargetSynthesisRunner,
            "run_target_synthesis": run_target_synthesis,
        }
        return mapping[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "ModernizationWorkflowEngine",
    "CognitiveExtractionRunner",
    "run_cognitive_chain",
    "TargetSynthesisRunner",
    "run_target_synthesis",
]
