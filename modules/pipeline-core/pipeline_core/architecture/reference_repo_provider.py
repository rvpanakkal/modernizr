"""
Reference Microservice Architecture Harvester Engine.
=====================================================
Inspects an approved reference enterprise microservice across four structural layers:
- Layer 1: Build & BOM (pom.xml dependencies, plugins, versions, build template)
- Layer 2: Package & Layering Topology (layering style, package hierarchy)
- Layer 3: Code Pattern Exemplars (cross-cutting controllers, exceptions, security, services)
- Layer 4: Executable Invariant Rules (ArchUnit assertions)

Produces an immutable, canonical ArchitectureProfile with a SHA-256 integrity hash.
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from pipeline_core.architecture.archunit_templates import get_standard_archunit_rules
from pipeline_core.architecture.provider_base import TargetArchitectureProvider
from pipeline_core.schemas.architecture import (
    ArchUnitRule,
    ArchitectureProfile,
    CodePatternExemplar,
    LayeringPattern,
)

log = logging.getLogger("ReferenceRepoProvider")


class ReferenceMicroserviceProvider(TargetArchitectureProvider):
    """
    Harvests an ArchitectureProfile from an existing Java / Spring Boot reference repository.
    """

    def build_profile(
        self,
        source_path_or_uri: str,
        profile_name: str,
        profile_id: Optional[str] = None,
    ) -> ArchitectureProfile:
        repo_path = Path(source_path_or_uri)
        temp_dir: Optional[tempfile.TemporaryDirectory] = None

        if not repo_path.exists():
            raise FileNotFoundError(f"Reference repository path does not exist: {source_path_or_uri}")

        if repo_path.is_file() and repo_path.suffix.lower() == ".zip":
            temp_dir = tempfile.TemporaryDirectory(prefix="ref_repo_")
            log.info("Extracting zip archive: %s -> %s", repo_path, temp_dir.name)
            with zipfile.ZipFile(repo_path, "r") as z:
                z.extractall(temp_dir.name)
            repo_path = Path(temp_dir.name)
            # In case the zip contains a single root folder, find it
            children = list(repo_path.iterdir())
            if len(children) == 1 and children[0].is_dir():
                repo_path = children[0]

        try:
            profile_slug = profile_id or self._generate_slug(profile_name)

            # Layer 1: Build & BOM
            build_info = self._harvest_layer1_build_and_bom(repo_path)

            # Layer 2: Package & Layering Topology
            topology_info = self._harvest_layer2_topology(repo_path)

            # Layer 3: Code Pattern Exemplars
            exemplars = self._harvest_layer3_exemplars(repo_path)

            # Layer 4: ArchUnit Conformance Rules
            conformance_rules = self._harvest_layer4_archunit_rules(repo_path)

            now = datetime.now(timezone.utc)
            profile = ArchitectureProfile(
                profile_id=profile_slug,
                name=profile_name,
                target_runtime=build_info["target_runtime"],
                created_at=now,
                base_package_pattern=topology_info["base_package_pattern"],
                layering_pattern=topology_info["layering_pattern"],
                build_file_template=build_info["build_file_template"],
                required_dependencies=build_info["required_dependencies"],
                exemplars=exemplars,
                conformance_rules=conformance_rules,
                sha256_hash="",
            )

            profile = profile.with_computed_hash()
            log.info(
                "[ReferenceMicroserviceProvider] Successfully harvested profile '%s' (ID: %s, Hash: %s...)",
                profile.name,
                profile.profile_id,
                profile.sha256_hash[:12],
            )
            return profile

        finally:
            if temp_dir is not None:
                temp_dir.cleanup()

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 1: Build & BOM Inspection
    # ─────────────────────────────────────────────────────────────────────────
    def _harvest_layer1_build_and_bom(self, repo_path: Path) -> Dict[str, Any]:
        pom_path = repo_path / "pom.xml"
        if not pom_path.exists():
            # Search subdirectories for pom.xml
            poms = list(repo_path.glob("**/pom.xml"))
            if poms:
                pom_path = poms[0]
            else:
                log.warning("No pom.xml found in %s; using default Spring Boot 3.5.x BOM", repo_path)
                return self._default_spring_boot_bom()

        pom_content = pom_path.read_text(encoding="utf-8")
        required_dependencies: List[str] = []
        spring_boot_version = "3.5.0"
        java_version = "21"

        try:
            # Parse XML stripping namespaces
            root = ET.fromstring(pom_content)
            # Helper to strip namespace from tag
            def strip_ns(tag: str) -> str:
                return tag.split("}")[-1] if "}" in tag else tag

            for elem in root.iter():
                elem.tag = strip_ns(elem.tag)

            # Check parent version
            parent = root.find("parent")
            if parent is not None:
                art = parent.find("artifactId")
                ver = parent.find("version")
                if art is not None and "spring-boot" in (art.text or ""):
                    if ver is not None and ver.text:
                        spring_boot_version = ver.text.strip()

            # Check properties for versions
            props = root.find("properties")
            if props is not None:
                for child in props:
                    child_tag = child.tag.lower()
                    if child_tag in ("java.version", "maven.compiler.source", "maven.compiler.target"):
                        if child.text:
                            java_version = child.text.strip()
                    elif "spring-boot.version" in child_tag and child.text:
                        spring_boot_version = child.text.strip()

            # Dependencies
            dependencies_elem = root.find("dependencies")
            if dependencies_elem is not None:
                for dep in dependencies_elem.findall("dependency"):
                    gid = dep.find("groupId")
                    aid = dep.find("artifactId")
                    if gid is not None and aid is not None and gid.text and aid.text:
                        required_dependencies.append(f"{gid.text.strip()}:{aid.text.strip()}")

        except Exception as e:
            log.warning("XML parsing failed for %s (%s); extracting via fallback regex", pom_path, e)
            dep_matches = re.findall(
                r"<groupId>\s*([^<]+)\s*</groupId>\s*<artifactId>\s*([^<]+)\s*</artifactId>",
                pom_content,
            )
            for gid, aid in dep_matches:
                coord = f"{gid.strip()}:{aid.strip()}"
                if coord not in required_dependencies:
                    required_dependencies.append(coord)

        # Build parameterized template from pom_content
        build_template = self._create_build_template(pom_content)

        return {
            "target_runtime": f"Java {java_version} / Spring Boot {spring_boot_version}",
            "spring_boot_version": spring_boot_version,
            "java_version": java_version,
            "required_dependencies": required_dependencies,
            "build_file_template": build_template,
        }

    def _create_build_template(self, original_pom: str) -> str:
        """
        Creates a reusable pom.xml template by parameterizing project coordinates.
        Preserves original comments, parent POM coordinates, dependency management, plugins, and dependencies.
        """
        parent_match = re.search(r"<parent>[\s\S]*?</parent>", original_pom)
        offset = parent_match.end() if parent_match else 0
        head = original_pom[:offset]
        tail = original_pom[offset:]

        tail = re.sub(
            r"(<groupId>)[^<]+(</groupId>)",
            r"\g<1>{{GROUP_ID}}\g<2>",
            tail,
            count=1,
        )
        tail = re.sub(
            r"(<artifactId>)[^<]+(</artifactId>)",
            r"\g<1>{{ARTIFACT_ID}}\g<2>",
            tail,
            count=1,
        )
        tail = re.sub(
            r"(<name>)[^<]+(</name>)",
            r"\g<1>{{PROJECT_NAME}}\g<2>",
            tail,
            count=1,
        )
        return head + tail

    def _default_spring_boot_bom(self) -> Dict[str, Any]:
        default_pom = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
    <modelVersion>4.0.0</modelVersion>
    <parent>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-starter-parent</artifactId>
        <version>3.5.0</version>
        <relativePath/>
    </parent>
    <groupId>{{GROUP_ID}}</groupId>
    <artifactId>{{ARTIFACT_ID}}</artifactId>
    <version>1.0.0-SNAPSHOT</version>
    <name>{{PROJECT_NAME}}</name>
    <description>Modernized Enterprise Microservice</description>

    <properties>
        <java.version>21</java.version>
        <archunit.version>1.3.0</archunit.version>
    </properties>

    <dependencies>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-web</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-validation</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-actuator</artifactId>
        </dependency>
        <dependency>
            <groupId>org.springframework.boot</groupId>
            <artifactId>spring-boot-starter-test</artifactId>
            <scope>test</scope>
        </dependency>
        <dependency>
            <groupId>com.tngtech.archunit</groupId>
            <artifactId>archunit-junit5</artifactId>
            <version>${archunit.version}</version>
            <scope>test</scope>
        </dependency>
    </dependencies>

    <build>
        <plugins>
            <plugin>
                <groupId>org.springframework.boot</groupId>
                <artifactId>spring-boot-maven-plugin</artifactId>
            </plugin>
        </plugins>
    </build>
</project>"""
        return {
            "target_runtime": "Java 21 / Spring Boot 3.5.0",
            "spring_boot_version": "3.5.0",
            "java_version": "21",
            "required_dependencies": [
                "org.springframework.boot:spring-boot-starter-web",
                "org.springframework.boot:spring-boot-starter-validation",
                "org.springframework.boot:spring-boot-starter-actuator",
                "com.tngtech.archunit:archunit-junit5",
            ],
            "build_file_template": default_pom,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 2: Package & Layering Topology
    # ─────────────────────────────────────────────────────────────────────────
    def _harvest_layer2_topology(self, repo_path: Path) -> Dict[str, Any]:
        java_files = list(repo_path.glob("**/*.java"))
        packages: Set[str] = set()

        for jf in java_files:
            try:
                content = jf.read_text(encoding="utf-8")
                match = re.search(r"^\s*package\s+([a-zA-Z0-9_.]+);", content, re.MULTILINE)
                if match:
                    packages.add(match.group(1).strip())
            except Exception:
                continue

        if not packages:
            return {
                "layering_pattern": LayeringPattern.CONTROLLER_SERVICE_REPOSITORY,
                "base_package_pattern": "com.enterprise.{domain}.v2",
            }

        # Analyze package segments
        all_tokens = set()
        for pkg in packages:
            all_tokens.update(pkg.split("."))

        layering_pattern = LayeringPattern.CONTROLLER_SERVICE_REPOSITORY
        if any(t in all_tokens for t in ("ports", "adapters", "hexagonal")):
            layering_pattern = LayeringPattern.HEXAGONAL
        elif any(t in all_tokens for t in ("clean", "infrastructure", "usecase", "domain_core")):
            layering_pattern = LayeringPattern.CLEAN_ARCHITECTURE
        elif "modular" in all_tokens or "modules" in all_tokens:
            layering_pattern = LayeringPattern.MODULAR_MONOLITH
        elif any(t in all_tokens for t in ("controller", "web", "service", "repository", "dao")):
            layering_pattern = LayeringPattern.CONTROLLER_SERVICE_REPOSITORY

        # Detect common prefix
        sorted_pkgs = sorted(list(packages))
        prefix_parts = sorted_pkgs[0].split(".")
        for pkg in sorted_pkgs[1:]:
            parts = pkg.split(".")
            common = []
            for a, b in zip(prefix_parts, parts):
                if a == b:
                    common.append(a)
                else:
                    break
            prefix_parts = common
            if not prefix_parts:
                break

        base_pkg = ".".join(prefix_parts) if prefix_parts else "com.enterprise"
        # If the base package ends with a specific layer name like controller/service, strip it
        layer_names = {"controller", "web", "service", "repository", "dao", "domain", "model", "config", "exception"}
        base_parts = [p for p in base_pkg.split(".") if p not in layer_names]
        clean_base = ".".join(base_parts)

        # Standardize base package pattern
        if "reference" in clean_base:
            base_package_pattern = clean_base.replace("reference", "{domain}")
        elif not clean_base.endswith("{domain}") and not clean_base.endswith("{domain}.v2"):
            base_package_pattern = f"{clean_base}.{{domain}}.v2"
        else:
            base_package_pattern = clean_base

        return {
            "layering_pattern": layering_pattern,
            "base_package_pattern": base_package_pattern,
            "detected_packages": sorted_pkgs,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 3: Code Pattern Exemplars
    # ─────────────────────────────────────────────────────────────────────────
    def _harvest_layer3_exemplars(self, repo_path: Path) -> List[CodePatternExemplar]:
        exemplars: List[CodePatternExemplar] = []
        java_files = list(repo_path.glob("src/main/java/**/*.java"))
        if not java_files:
            java_files = list(repo_path.glob("**/*.java"))

        for jf in java_files:
            # Skip test files for exemplar harvesting
            if "src" in jf.parts and "test" in jf.parts:
                continue

            try:
                content = jf.read_text(encoding="utf-8")
            except Exception:
                continue

            rel_path = str(jf.relative_to(repo_path)).replace("\\", "/")

            # 1. Global Exception Handler (@RestControllerAdvice / @ControllerAdvice)
            if "@RestControllerAdvice" in content or "@ControllerAdvice" in content:
                ann = ["@RestControllerAdvice"] if "@RestControllerAdvice" in content else ["@ControllerAdvice"]
                sanitized = self._sanitize_java_code(content)
                exemplars.append(
                    CodePatternExemplar(
                        pattern_name="GlobalExceptionHandler",
                        target_layer="controller",
                        annotations_matched=ann,
                        code_snippet=sanitized,
                        origin_file=rel_path,
                    )
                )

            # 2. REST Controller (@RestController)
            elif "@RestController" in content:
                ann = ["@RestController"]
                if "@RequestMapping" in content:
                    ann.append("@RequestMapping")
                sanitized = self._sanitize_java_code(content)
                exemplars.append(
                    CodePatternExemplar(
                        pattern_name="RestController",
                        target_layer="controller",
                        annotations_matched=ann,
                        code_snippet=sanitized,
                        origin_file=rel_path,
                    )
                )

            # 3. Security Config / Web Configuration (@Configuration)
            elif "@Configuration" in content:
                ann = ["@Configuration"]
                p_name = "SecurityConfig" if "Security" in jf.stem or "SecurityFilterChain" in content else "Configuration"
                sanitized = self._sanitize_java_code(content)
                exemplars.append(
                    CodePatternExemplar(
                        pattern_name=p_name,
                        target_layer="config",
                        annotations_matched=ann,
                        code_snippet=sanitized,
                        origin_file=rel_path,
                    )
                )

            # 4. Domain Service (@Service)
            elif "@Service" in content:
                ann = ["@Service"]
                if "@Transactional" in content:
                    ann.append("@Transactional")
                sanitized = self._sanitize_java_code(content)
                exemplars.append(
                    CodePatternExemplar(
                        pattern_name="Service",
                        target_layer="service",
                        annotations_matched=ann,
                        code_snippet=sanitized,
                        origin_file=rel_path,
                    )
                )

            # 5. Domain Entity / Repository
            elif "@Entity" in content or "@Table" in content:
                ann = ["@Entity"]
                sanitized = self._sanitize_java_code(content)
                exemplars.append(
                    CodePatternExemplar(
                        pattern_name="AuditedEntity",
                        target_layer="domain",
                        annotations_matched=ann,
                        code_snippet=sanitized,
                        origin_file=rel_path,
                    )
                )

        return exemplars

    def _sanitize_java_code(self, source_code: str) -> str:
        """
        Strips license blocks, author tags, and file-specific noise,
        retaining structure, imports, annotations, and methods.
        """
        # Strip block comments at top of file (licenses, copyrights)
        code = re.sub(r"/\*[\s\S]*?(?:Copyright|License|All\s+rights\s+reserved)[\s\S]*?\*/", "", source_code, flags=re.IGNORECASE)
        # Strip author javadoc tags
        code = re.sub(r"@author\s+.*", "", code)
        # Strip trailing blank lines
        return code.strip()

    # ─────────────────────────────────────────────────────────────────────────
    # Layer 4: ArchUnit Rule Harvesting
    # ─────────────────────────────────────────────────────────────────────────
    def _harvest_layer4_archunit_rules(self, repo_path: Path) -> List[ArchUnitRule]:
        arch_test_files = list(repo_path.glob("**/*ArchTest.java")) + list(repo_path.glob("**/*ArchitectureTest.java"))
        harvested_rules: List[ArchUnitRule] = []

        for atf in arch_test_files:
            try:
                content = atf.read_text(encoding="utf-8")
                # Look for public static final ArchRule <name> = ...;
                matches = re.findall(
                    r"@ArchTest\s+public\s+static\s+final\s+ArchRule\s+([a-zA-Z0-9_]+)\s*=\s*([\s\S]*?);",
                    content,
                )
                for name, rule_body in matches:
                    desc_match = re.search(r'\.because\("([^"]+)"\)', rule_body)
                    description = desc_match.group(1) if desc_match else f"ArchUnit invariant rule: {name}"
                    rule_id = f"ARCH-{name.upper().replace('_', '-')[:30]}"
                    harvested_rules.append(
                        ArchUnitRule(
                            rule_id=rule_id,
                            description=description,
                            test_method_name=name,
                            rule_code=rule_body.strip(),
                        )
                    )
            except Exception as e:
                log.warning("Failed parsing ArchUnit rules from %s: %s", atf, e)

        if not harvested_rules:
            log.info("No existing ArchUnit test files found in %s; injecting enterprise baseline rules", repo_path)
            return get_standard_archunit_rules()

        # If harvested rules don't cover standard invariants, merge them
        existing_ids = {r.rule_id for r in harvested_rules}
        for std in get_standard_archunit_rules():
            if std.rule_id not in existing_ids and not any(std.test_method_name == r.test_method_name for r in harvested_rules):
                harvested_rules.append(std)

        return harvested_rules

    def _generate_slug(self, name: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.strip().lower()).strip("-")
        return f"arch-{slug}" if not slug.startswith("arch-") else slug
