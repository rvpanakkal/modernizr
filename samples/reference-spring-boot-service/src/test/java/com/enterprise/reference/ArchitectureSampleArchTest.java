package com.enterprise.reference;

import com.tngtech.archunit.core.importer.ImportOption;
import com.tngtech.archunit.junit.AnalyzeClasses;
import com.tngtech.archunit.junit.ArchTest;
import com.tngtech.archunit.lang.ArchRule;

import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.classes;
import static com.tngtech.archunit.lang.syntax.ArchRuleDefinition.noClasses;

@AnalyzeClasses(packages = "com.enterprise.reference", importOptions = {ImportOption.DoNotIncludeTests.class})
public class ArchitectureSampleArchTest {

    @ArchTest
    public static final ArchRule controllers_must_not_access_repositories_directly =
        noClasses()
            .that().resideInAPackage("..controller..")
            .should().dependOnClassesThat().resideInAPackage("..repository..")
            .because("Controllers must interact with repositories only through domain services");

    @ArchTest
    public static final ArchRule services_must_be_annotated_with_service =
        classes()
            .that().resideInAPackage("..service..")
            .and().areTopLevelClasses()
            .should().beAnnotatedWith(org.springframework.stereotype.Service.class)
            .because("Business domain services must declare Spring bean boundaries");
}
