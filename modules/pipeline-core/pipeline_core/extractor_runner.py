"""
Execution runner for OpenRewrite Lossless Semantic Tree (LST) Metadata Extractor.
Invokes the Java lst-extractor shaded JAR (or fallback) against actual Java source code
and parses real extracted metadata into structured domain representations.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pipeline_core.paths import artifacts_root, sha256_file

log = logging.getLogger(__name__)


def find_repo_root() -> Path:
    """Finds the root repository path."""
    current = Path(__file__).resolve().parent
    for _ in range(5):
        if (current / "modules" / "lst-extractor").exists():
            return current
        current = current.parent
    return Path.cwd()


def find_lst_extractor_jar() -> Optional[Path]:
    """Locates the shaded lst-extractor JAR."""
    repo_root = find_repo_root()
    jar_path = repo_root / "modules" / "lst-extractor" / "target" / "lst-extractor-1.0.0-SNAPSHOT.jar"
    if jar_path.exists():
        return jar_path

    # Try any jar under target
    target_dir = repo_root / "modules" / "lst-extractor" / "target"
    if target_dir.exists():
        jars = [j for j in target_dir.glob("*.jar") if not j.name.startswith("original-")]
        if jars:
            return jars[0]

    return None


def classify_class_role(simple_name: str, annotations: List[str], kind: str) -> str:
    """Classifies an extracted class into its architectural layer role."""
    ann_set = set(annotations)

    if any(a in ann_set for a in ("ManagedBean", "Named", "Controller", "RestController", "Path", "WebServlet")):
        return "PRESENTATION"
    if any(a in ann_set for a in ("Stateless", "Stateful", "Service", "Transactional")) or simple_name.endswith("Service"):
        return "BUSINESS_SERVICE"
    if any(a in ann_set for a in ("PersistenceContext", "Repository")) or simple_name.endswith("Repository") or simple_name.endswith("DAO"):
        return "DATA_ACCESS"
    if simple_name.endswith("Gateway") or "Gateway" in simple_name or "Connector" in simple_name:
        return "GATEWAY"
    if any(a in ann_set for a in ("Entity", "Table", "Embeddable")):
        return "DOMAIN_ENTITY"
    if "Filter" in simple_name or "Principal" in simple_name or "Auth" in simple_name:
        return "SECURITY"
    if kind == "INTERFACE":
        return "INTERFACE"
    return "DOMAIN_MODEL"


def run_java_lst_extractor(source_dir: Path, output_file: Path) -> bool:
    """Runs the Java lst-extractor CLI via subprocess."""
    jar_path = find_lst_extractor_jar()
    repo_root = find_repo_root()

    if jar_path and jar_path.exists():
        cmd = [
            "java",
            "-jar",
            str(jar_path),
            "--source-dir",
            str(source_dir),
            "--output",
            str(output_file),
        ]
        log.info("[LST Runner] Executing shaded JAR: %s", " ".join(cmd))
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=120)
            if res.returncode == 0 and output_file.exists():
                log.info("[LST Runner] ✓ Java extractor completed successfully.")
                return True
            log.warning(
                "[LST Runner] Java extractor returned code %d. Stdout: %s, Stderr: %s",
                res.returncode,
                res.stdout[:500],
                res.stderr[:500],
            )
        except Exception as exc:
            log.warning("[LST Runner] Execution of JAR failed: %s", exc)

    # Fallback to mvn exec:java if available
    pom_file = repo_root / "modules" / "lst-extractor" / "pom.xml"
    if pom_file.exists() and shutil.which("mvn"):
        log.info("[LST Runner] Attempting fallback via mvn exec:java...")
        mvn_cmd = [
            "mvn",
            "exec:java",
            "-f",
            str(pom_file),
            "-Dexec.mainClass=com.enterprise.modernization.rewrite.ExtractorCli",
            f"-Dexec.args=--source-dir {source_dir} --output {output_file}",
        ]
        try:
            res = subprocess.run(mvn_cmd, capture_output=True, text=True, check=False, timeout=180)
            if res.returncode == 0 and output_file.exists():
                return True
        except Exception as exc:
            log.warning("[LST Runner] mvn exec:java failed: %s", exc)

    return False


def fallback_python_source_scanner(source_dir: Path, output_file: Path) -> Dict[str, Any]:
    """
    Lightweight Python-based AST fallback scanner when Java runtime is unavailable.
    Inspects .java files in source_dir and produces valid LST JSON metadata.
    """
    log.info("[LST Runner] Using Python fallback scanner for source: %s", source_dir)
    classes: List[Dict[str, Any]] = []

    java_files = list(source_dir.rglob("*.java"))
    for jf in java_files:
        try:
            content = jf.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        pkg_match = re.search(r"package\s+([\w\.]+);", content)
        pkg = pkg_match.group(1) if pkg_match else "default"

        class_match = re.search(r"(public\s+)?(class|interface|enum)\s+(\w+)", content)
        if not class_match:
            continue

        kind = class_match.group(2).upper()
        simple_name = class_match.group(3)
        fqn = f"{pkg}.{simple_name}" if pkg != "default" else simple_name

        annotations = re.findall(r"@(\w+)", content)
        clean_annotations = list(dict.fromkeys(annotations))

        fields: List[Dict[str, Any]] = []
        for f_match in re.finditer(r"@(Inject|EJB|Autowired|PersistenceContext|Resource)\s*(?:private|protected|public)?\s+(\w+)\s+(\w+);", content):
            fields.append({
                "name": f_match.group(3),
                "type": f_match.group(2),
                "annotation": f_match.group(1),
            })

        methods: List[Dict[str, Any]] = []
        for m_match in re.finditer(r"(?:public|protected|private)?\s+(?:static\s+)?([\w<>]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:throws\s+[\w,\s]+)?\s*\{", content):
            ret_type = m_match.group(1)
            m_name = m_match.group(2)
            if m_name in ("if", "for", "while", "switch", "catch"):
                continue
            raw_params = m_match.group(3).strip()
            param_types = [p.strip().split()[0] for p in raw_params.split(",") if p.strip()] if raw_params else []
            methods.append({
                "name": m_name,
                "returnType": ret_type,
                "parameterTypes": param_types,
                "annotations": [],
                "signature": f"{fqn}.{m_name}({','.join(param_types)})",
                "branchCount": content.count("if ") + content.count("for ") + content.count("while "),
            })

        classes.append({
            "fqn": fqn,
            "simpleName": simple_name,
            "kind": kind,
            "annotations": clean_annotations,
            "fields": fields,
            "methods": methods,
            "invocations": [],
        })

    payload = {
        "schemaVersion": "1.0.0",
        "extractedAt": datetime.now(timezone.utc).isoformat(),
        "sourceDirectory": str(source_dir),
        "classes": classes,
    }

    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def execute_lst_extractor(
    source_dir_or_path: str | Path,
    output_file: Optional[str | Path] = None,
    monolith_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Executes the OpenRewrite LST extractor on real code and returns enriched real statistics.
    """
    repo_root = find_repo_root()
    src_path = Path(source_dir_or_path)
    if not src_path.is_absolute():
        src_path = repo_root / src_path

    if not src_path.exists():
        raise FileNotFoundError(f"Source directory does not exist: {src_path}")

    # If directory has src/main/java subfolder, point to it
    if (src_path / "src" / "main" / "java").exists():
        effective_src = src_path / "src" / "main" / "java"
    else:
        effective_src = src_path

    out_path = Path(output_file) if output_file else (repo_root / "artifacts" / "raw_lst" / "metadata_extracted.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    start_time = time.time()
    success = run_java_lst_extractor(effective_src, out_path)

    if not success or not out_path.exists():
        payload = fallback_python_source_scanner(effective_src, out_path)
    else:
        with open(out_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

    duration_ms = int((time.time() - start_time) * 1000)
    raw_classes = payload.get("classes", [])

    # Process class records and roles
    class_summaries: List[Dict[str, Any]] = []
    total_methods = 0
    total_fields = 0
    total_invocations = 0
    endpoints_count = 0
    gateways_count = 0

    for c in raw_classes:
        simple_name = c.get("simpleName", "")
        annotations = c.get("annotations", [])
        kind = c.get("kind", "CLASS")
        role = classify_class_role(simple_name, annotations, kind)

        m_count = len(c.get("methods", []))
        f_count = len(c.get("fields", []))
        inv_count = len(c.get("invocations", []))

        total_methods += m_count
        total_fields += f_count
        total_invocations += inv_count

        if role == "PRESENTATION":
            endpoints_count += 1
        elif role == "GATEWAY":
            gateways_count += 1

        injected_types = [f.get("type", "") for f in c.get("fields", []) if f.get("type")]

        class_summaries.append({
            "fqn": c.get("fqn", ""),
            "simple_name": simple_name,
            "kind": kind,
            "role": role,
            "annotations": annotations,
            "methods_count": m_count,
            "fields_count": f_count,
            "invocations_count": inv_count,
            "injected_dependencies": injected_types,
        })

    # Sort classes logically: PRESENTATION first, then BUSINESS_SERVICE, etc.
    role_priority = {
        "PRESENTATION": 1,
        "BUSINESS_SERVICE": 2,
        "DATA_ACCESS": 3,
        "GATEWAY": 4,
        "SECURITY": 5,
        "DOMAIN_ENTITY": 6,
        "DOMAIN_MODEL": 7,
        "INTERFACE": 8,
    }
    class_summaries.sort(key=lambda x: (role_priority.get(x["role"], 9), x["simple_name"]))

    digest = sha256_file(out_path)

    return {
        "monolith_id": monolith_id or effective_src.stem or "legacy-monolith",
        "source_dir": str(effective_src),
        "output_file": str(out_path),
        "classes_count": len(raw_classes),
        "methods_count": total_methods,
        "injected_fields_count": total_fields,
        "invocations_count": total_invocations,
        "endpoints_count": endpoints_count,
        "cics_gateways_count": gateways_count,
        "sha256_digest": digest,
        "extracted_at": payload.get("extractedAt", datetime.now(timezone.utc).isoformat()),
        "execution_time_ms": duration_ms,
        "classes": class_summaries,
    }
