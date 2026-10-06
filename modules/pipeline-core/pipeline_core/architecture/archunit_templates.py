"""
Standard ArchUnit Invariant Rule Templates and Generator.
=========================================================
Provides:
- Standard enterprise ArchUnit rules for Spring Boot 3.5 architectures.
- Dynamic generation of standalone ArchitectureConformanceTest.java source files
  for Step 5.5 conformance gating.
"""

from __future__ import annotations

import re
from typing import List, Optional

from pipeline_core.schemas.architecture import ArchUnitRule, ArchitectureProfile

STANDARD_RULES: List[ArchUnitRule] = [
    ArchUnitRule(
        rule_id="ARCH-001",
        description="Controllers must only access Services and must not depend directly on Repositories.",
        test_method_name="controllers_should_not_access_repositories_directly",
        rule_code=(
            "noClasses()\n"
            '        .that().resideInAPackage("..controller..")\n'
            '        .or().resideInAPackage("..web..")\n'
            '        .should().dependOnClassesThat().resideInAPackage("..repository..")\n'
            '        .because("Controllers must interact with repositories only through domain services")'
        ),
    ),
    ArchUnitRule(
        rule_id="ARCH-002",
        description="Domain services must declare Spring Service or Transactional boundaries.",
        test_method_name="services_should_be_annotated_with_service_or_transactional",
        rule_code=(
            "classes()\n"
            '        .that().resideInAPackage("..service..")\n'
            "        .and().areTopLevelClasses()\n"
            "        .and().areNotInterfaces()\n"
            "        .should().beAnnotatedWith(org.springframework.stereotype.Service.class)\n"
            "        .orShould().beAnnotatedWith(org.springframework.transaction.annotation.Transactional.class)\n"
            '        .because("Business domain services must declare Spring bean or transaction boundaries")'
        ),
    ),
    ArchUnitRule(
        rule_id="ARCH-003",
        description="Domain JPA/persistence entities must not be accessed directly by presentation controllers.",
        test_method_name="controllers_should_not_access_entities_directly",
        rule_code=(
            "noClasses()\n"
            '        .that().resideInAPackage("..controller..")\n'
            '        .or().resideInAPackage("..web..")\n'
            '        .should().dependOnClassesThat().resideInAPackage("..domain..")\n'
            '        .orShould().dependOnClassesThat().resideInAPackage("..entity..")\n'
            '        .because("Presentation controllers must communicate exclusively via DTOs and records")'
        ),
    ),
    ArchUnitRule(
        rule_id="ARCH-004",
        description="Classes in controller packages must have names ending with 'Controller'.",
        test_method_name="controller_classes_should_be_named_ending_with_controller",
        rule_code=(
            "classes()\n"
            '        .that().resideInAPackage("..controller..")\n'
            "        .and().areTopLevelClasses()\n"
            '        .should().haveSimpleNameEndingWith("Controller")\n'
            '        .because("Controller classes must follow enterprise naming conventions")'
        ),
    ),
]


def get_standard_archunit_rules() -> List[ArchUnitRule]:
    """Returns a copy of standard enterprise ArchUnit rules."""
    return [rule.model_copy() for rule in STANDARD_RULES]


def render_archunit_test_class(
    profile: ArchitectureProfile,
    package_name: Optional[str] = None,
    scan_package: Optional[str] = None,
) -> str:
    """
    Renders an executable Java ArchUnit JUnit 5 test class embedding the profile's conformance rules.
    """
    pkg = package_name or "com.enterprise.modernization"
    scan = scan_package or profile.base_package_pattern.replace("{domain}", "modernization").replace(".v2", "")
    # Sanitize scan package: strip placeholders if any remain
    scan = re.sub(r"\{.*?\}", "modernization", scan).rstrip(".")

    rules = profile.conformance_rules if profile.conformance_rules else get_standard_archunit_rules()

    rule_fields = []
    for r in rules:
        rule_code = r.rule_code.rstrip(";")
        field_block = (
            f"    /**\n"
            f"     * [{r.rule_id}] {r.description}\n"
            f"     */\n"
            f"    @ArchTest\n"
            f"    public static final ArchRule {r.test_method_name} =\n"
            f"        {rule_code};\n"
        )
        rule_fields.append(field_block)

    rules_content = "\n".join(rule_fields)

    return f"""package {pkg};

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

/**
 * Step 5.5 Architectural Conformance Verification Gate.
 * =======================================================
 * Governed by Architecture Profile: {profile.name} (ID: {profile.profile_id})
 * Integrity Checksum (SHA-256): {profile.sha256_hash or 'UNSET'}
 * Layering Pattern: {profile.layering_pattern.value}
 * Target Runtime: {profile.target_runtime}
 *
 * Verifies that the synthesized target Spring Boot microservice strictly adheres
 * to the structural invariants, dependency directions, and layering boundaries
 * extracted from the reference architecture.
 */
@AnalyzeClasses(packages = "{scan}", importOptions = {{ImportOption.DoNotIncludeTests.class}})
public class ArchitectureConformanceTest {{

{rules_content}
}}
"""
